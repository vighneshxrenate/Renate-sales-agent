import asyncio
import re
from urllib.parse import quote_plus, urljoin

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadEmail, LeadPhone
from app.scraper.browser_pool import BrowserPool
from app.scraper.proxy_pool import ProxyPool
from app.services.email_discovery import EmailDiscoveryService
from app.services.hunter_client import HunterClient
from app.utils.email_patterns import (
    extract_domain,
    extract_emails_from_text,
    extract_phones_from_text,
)

logger = structlog.get_logger()

CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us"]

GOOGLE_CONSENT_COOKIES = [
    {"name": "CONSENT", "value": "YES+cb.20231008-07-p0.en+FX+410", "domain": ".google.co.in", "path": "/"},
]

PHONE_RE = re.compile(
    r"(?:"
    r"(?:\+91[\s\-]?)?(?:\(?0\d{2,4}\)?[\s\-.]?)\d{3,4}[\s\-.]?\d{3,4}"
    r"|1800[\s\-]?\d{3}[\s\-]?\d{3,4}"
    r"|\+91[\s\-]?\d{4,5}[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
    r"|\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
    r")",
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

JUNK_EMAIL_DOMAINS = {
    "example.com", "test.com", "sentry.io", "googleapis.com", "w3.org",
    "schema.org", "cloudflare.com", "gstatic.com", "google.com",
    "facebook.com", "twitter.com", "youtube.com", "github.com",
    "wikipedia.org", "mozilla.org", "apple.com", "microsoft.com",
}


class EnrichmentService:
    def __init__(self) -> None:
        self._hunter = HunterClient()
        self._email_discovery = EmailDiscoveryService()

    async def enrich_lead(
        self,
        lead: Lead,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
        db: AsyncSession,
    ) -> None:
        existing_emails: set[str] = set()
        existing_phones: set[str] = set()

        new_emails: list[tuple[str, str, str]] = []
        new_phones: list[tuple[str, str]] = []
        domain = None

        # === STEP 1: Hunter.io (HR first, then general fallback) ===
        if self._hunter.available:
            domain, hr_emails = await self._hunter.company_search(
                lead.company_name, limit=10, department="hr"
            )

            if domain and not lead.website:
                lead.website = f"https://{domain}"

            hr_count = 0
            for entry in hr_emails:
                email = entry.get("value")
                if not email or email.lower() in existing_emails:
                    continue
                first_name = entry.get("first_name", "")
                last_name = entry.get("last_name", "")
                source_detail = f"hunter:{first_name} {last_name}".strip() if (first_name or last_name) else "hunter"
                new_emails.append((email, "hr", source_detail))
                existing_emails.add(email.lower())
                hr_count += 1

                phone = entry.get("phone_number")
                if phone and phone not in existing_phones:
                    new_phones.append((phone, "mobile"))
                    existing_phones.add(phone)

            if hr_count == 0:
                fallback_domain, fallback_emails = await self._hunter.company_search(
                    lead.company_name, limit=5
                )
                if fallback_domain and not lead.website:
                    lead.website = f"https://{fallback_domain}"
                domain = domain or fallback_domain

                for entry in fallback_emails:
                    email = entry.get("value")
                    if not email or email.lower() in existing_emails:
                        continue
                    first_name = entry.get("first_name", "")
                    last_name = entry.get("last_name", "")
                    position = (entry.get("position") or "").lower()
                    department = (entry.get("department") or "").lower()
                    hr_kw = ("hr", "recruit", "talent", "hiring", "people", "human resource")
                    etype = "hr" if any(kw in position + department for kw in hr_kw) else "personal"
                    source_detail = f"hunter:{first_name} {last_name}".strip() if (first_name or last_name) else "hunter"
                    new_emails.append((email, etype, source_detail))
                    existing_emails.add(email.lower())

                    phone = entry.get("phone_number")
                    if phone and phone not in existing_phones:
                        new_phones.append((phone, "mobile"))
                        existing_phones.add(phone)

            logger.info(
                "hunter_enrichment_done",
                company=lead.company_name,
                domain=domain,
                hr_emails=hr_count,
                total_emails=len(new_emails),
            )

        # Derive domain from website if Hunter didn't find it
        if not domain and lead.website:
            domain = extract_domain(lead.website)

        # === STEP 2: Free fallback — Google dork + SMTP verify (emails + phones) ===
        hr_email_count = sum(1 for _, t, _ in new_emails if t == "hr")
        if hr_email_count == 0 and browser_pool:
            discovered = await self._email_discovery.discover_emails(
                lead.company_name, domain, browser_pool
            )
            for email, etype, source in discovered:
                if email.lower() not in existing_emails:
                    new_emails.append((email, etype, source))
                    existing_emails.add(email.lower())

        # === STEP 3: Google search for phone + email in one session ===
        if browser_pool:
            location = lead.location or "India"
            g_phones, g_emails = await self._google_search_contacts(
                lead.company_name, domain, location, browser_pool
            )
            for phone, ptype in g_phones:
                cleaned = re.sub(r"[\s\-\(\).]", "", phone)
                if cleaned not in existing_phones:
                    new_phones.append((phone, ptype))
                    existing_phones.add(cleaned)
            for email, etype in g_emails:
                if email.lower() not in existing_emails:
                    new_emails.append((email, etype, "google"))
                    existing_emails.add(email.lower())

        # === STEP 4: Scrape contact pages for remaining phones/emails ===
        website = lead.website
        if website and browser_pool and not new_phones:
            page_texts = await self._scrape_contact_pages(website, browser_pool)
            for text in page_texts:
                for email, etype in extract_emails_from_text(text):
                    if email.lower() not in existing_emails:
                        new_emails.append((email, etype, "scraped"))
                        existing_emails.add(email.lower())
                for phone, ptype in extract_phones_from_text(text):
                    cleaned = re.sub(r"[\s\-\(\).]", "", phone)
                    if cleaned not in existing_phones:
                        new_phones.append((phone, ptype))
                        existing_phones.add(cleaned)

        # === STEP 5: Store ===
        for email, etype, source in new_emails:
            db.add(LeadEmail(
                lead_id=lead.id,
                email=email,
                email_type=etype,
                source=source,
                verified=False,
            ))

        for phone, ptype in new_phones:
            db.add(LeadPhone(
                lead_id=lead.id,
                phone=phone,
                phone_type=ptype,
            ))

        if new_emails or new_phones:
            await db.flush()
            logger.info(
                "lead_enriched",
                lead_id=str(lead.id),
                company=lead.company_name,
                new_emails=len(new_emails),
                new_phones=len(new_phones),
            )

    async def _google_search_contacts(
        self,
        company_name: str,
        domain: str | None,
        location: str,
        browser_pool: BrowserPool,
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """Single Google session to find both phone numbers and emails."""
        phones: list[tuple[str, str]] = []
        emails: list[tuple[str, str]] = []
        phone_seen: set[str] = set()
        email_seen: set[str] = set()

        ctx = await browser_pool.acquire(stealth_level="minimal", proxy=None)
        try:
            page = await ctx.context.new_page()
            await ctx.context.add_cookies(GOOGLE_CONSENT_COOKIES)
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            queries = [
                f"{company_name} {location} phone number contact hr email",
            ]
            if domain:
                queries.append(f'"{company_name}" "@{domain}" hr OR recruiter OR contact phone')

            for query in queries[:2]:
                try:
                    url = f"https://www.google.co.in/search?q={quote_plus(query)}&num=20&hl=en"
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(2000)

                    text = await page.inner_text("body")
                    if "unusual traffic" in text.lower():
                        logger.warning("google_contacts_blocked", company=company_name)
                        break

                    html = await page.content()
                    combined = html + " " + text

                    # Extract phones
                    for phone in PHONE_RE.findall(combined):
                        cleaned = re.sub(r"[\s\-\(\).]", "", phone)
                        if cleaned in phone_seen or len(cleaned) < 8:
                            continue
                        # Skip junk numbers
                        digits_only = re.sub(r"\D", "", cleaned)
                        if len(set(digits_only)) <= 3:
                            continue
                        # Must start with valid prefix: +91, 0, 1800, or +country code
                        if not (digits_only.startswith("91") or digits_only.startswith("0")
                                or digits_only.startswith("1800") or cleaned.startswith("+")):
                            continue
                        phone_seen.add(cleaned)
                        ptype = "toll_free" if cleaned.startswith("1800") else "main"
                        phones.append((phone.strip(), ptype))

                    # Extract emails
                    for email in EMAIL_RE.findall(combined):
                        email_lower = email.lower()
                        email_domain = email_lower.split("@")[1]
                        if email_domain in JUNK_EMAIL_DOMAINS or email_lower in email_seen:
                            continue
                        local_part = email_lower.split("@")[0]
                        if ("%" in email or "+" in email or email.startswith(".")
                                or "u003e" in email_lower or len(local_part) < 3
                                or local_part in ("name", "email", "your", "user", "test", "info")):
                            continue
                        is_relevant = (domain and domain in email_domain) or email_domain in (
                            "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "rediffmail.com"
                        )
                        if not is_relevant:
                            continue
                        email_seen.add(email_lower)
                        local = email_lower.split("@")[0]
                        hr_kw = ("hr", "recruit", "talent", "hiring", "career", "people")
                        etype = "hr" if any(kw in local for kw in hr_kw) else "personal"
                        emails.append((email, etype))

                    await asyncio.sleep(2)
                except Exception:
                    logger.warning("google_contacts_query_failed", company=company_name)

            await page.close()
        except Exception:
            logger.warning("google_contacts_search_failed", company=company_name)
        finally:
            await browser_pool.release(ctx)

        if phones or emails:
            logger.info("google_contacts_found", company=company_name, phones=len(phones), emails=len(emails))

        return phones[:3], emails[:5]

    async def _scrape_contact_pages(
        self, website: str, browser_pool: BrowserPool
    ) -> list[str]:
        if not website.startswith("http"):
            website = f"https://{website}"

        texts: list[str] = []
        ctx = await browser_pool.acquire(stealth_level="minimal", proxy=None)

        try:
            page = await ctx.context.new_page()
            for path in CONTACT_PATHS:
                url = urljoin(website, path)
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                    if resp and resp.status == 200:
                        text = await page.inner_text("body")
                        texts.append(text)
                except Exception:
                    continue
            await page.close()
        except Exception:
            logger.debug("enrichment_scrape_failed", website=website)
        finally:
            await browser_pool.release(ctx)

        return texts
