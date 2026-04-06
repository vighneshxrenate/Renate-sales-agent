import asyncio
import re
from urllib.parse import quote_plus, urljoin

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadEmail, LeadPhone
from app.scraper.browser_pool import BrowserPool
from app.scraper.proxy_pool import ProxyPool
from app.services.apollo_client import ApolloClient
from app.services.email_discovery import EmailDiscoveryService
from app.services.hunter_client import HunterClient
from app.utils.email_patterns import (
    extract_domain,
    extract_emails_from_text,
    extract_phones_from_text,
)
from app.utils.phone_validator import is_valid_indian_phone

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

# Valid Indian landline area codes (major cities)
INDIAN_AREA_CODES = {"011", "022", "033", "040", "044", "080", "020", "079", "0124", "0120", "0172", "0141"}


def _is_valid_phone(phone: str) -> bool:
    return is_valid_indian_phone(phone)


def _is_valid_email(email: str) -> bool:
    local = email.lower().split("@")[0]
    domain = email.lower().split("@")[1]
    if domain in JUNK_EMAIL_DOMAINS:
        return False
    if len(local) < 3:
        return False
    if "%" in email or "+" in email or email.startswith(".") or "u003e" in email.lower():
        return False
    if local in ("name", "email", "your", "user", "test", "info", "example", "abc"):
        return False
    return True


class EnrichmentService:
    def __init__(self) -> None:
        self._apollo = ApolloClient()
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

        # === STEP 1: Apollo.io — people search (paid) + org enrich (free) ===
        if self._apollo.available:
            # Try people search (works on paid plan only)
            people = await self._apollo.search_hr_contacts(lead.company_name, limit=5)
            for person in people:
                email = person.get("email")
                if email and email.lower() not in existing_emails and _is_valid_email(email):
                    title = (person.get("title") or "").lower()
                    first = person.get("first_name", "")
                    last = person.get("last_name", "")
                    hr_kw = ("hr", "recruit", "talent", "hiring", "people", "human")
                    etype = "hr" if any(kw in title for kw in hr_kw) else "personal"
                    source = f"apollo:{first} {last} — {person.get('title', '')}".strip()
                    new_emails.append((email, etype, source))
                    existing_emails.add(email.lower())

                phone = person.get("phone_number") or person.get("sanitized_phone")
                if phone and phone not in existing_phones:
                    new_phones.append((phone, "mobile"))
                    existing_phones.add(phone)

                org = person.get("organization", {})
                if org and not domain:
                    domain = org.get("primary_domain")

            # Org enrich — works on free plan, gets domain + company phone
            if not domain:
                org_data = await self._apollo.enrich_company(lead.company_name)
                if org_data:
                    domain = org_data.get("primary_domain")
                    phone = org_data.get("phone")
                    if phone and phone not in existing_phones and _is_valid_phone(phone):
                        new_phones.append((phone, "main"))
                        existing_phones.add(phone)

            if domain and not lead.website:
                lead.website = f"https://{domain}"

            if people or domain:
                logger.info("apollo_enrichment_done", company=lead.company_name, domain=domain, people=len(people))

        # === STEP 2: Hunter.io — secondary, HR department filter ===
        hr_email_count = sum(1 for _, t, _ in new_emails if t == "hr")
        if hr_email_count == 0 and self._hunter.available:
            h_domain, hr_emails = await self._hunter.company_search(
                lead.company_name, limit=10, department="hr"
            )
            if h_domain and not domain:
                domain = h_domain
            if h_domain and not lead.website:
                lead.website = f"https://{h_domain}"

            for entry in hr_emails:
                email = entry.get("value")
                if not email or email.lower() in existing_emails or not _is_valid_email(email):
                    continue
                first = entry.get("first_name", "")
                last = entry.get("last_name", "")
                source = f"hunter:{first} {last}".strip() if (first or last) else "hunter"
                new_emails.append((email, "hr", source))
                existing_emails.add(email.lower())

            # General fallback if no HR found
            if not hr_emails:
                fb_domain, fb_emails = await self._hunter.company_search(lead.company_name, limit=5)
                if fb_domain and not domain:
                    domain = fb_domain
                if fb_domain and not lead.website:
                    lead.website = f"https://{fb_domain}"
                for entry in fb_emails:
                    email = entry.get("value")
                    if not email or email.lower() in existing_emails or not _is_valid_email(email):
                        continue
                    first = entry.get("first_name", "")
                    last = entry.get("last_name", "")
                    pos = (entry.get("position") or "").lower()
                    dept = (entry.get("department") or "").lower()
                    hr_kw = ("hr", "recruit", "talent", "hiring", "people", "human")
                    etype = "hr" if any(kw in pos + dept for kw in hr_kw) else "personal"
                    source = f"hunter:{first} {last}".strip() if (first or last) else "hunter"
                    new_emails.append((email, etype, source))
                    existing_emails.add(email.lower())

            logger.info("hunter_enrichment_done", company=lead.company_name, domain=domain, emails=len(new_emails))

        # Derive domain from website if APIs didn't find it
        if not domain and lead.website:
            domain = extract_domain(lead.website)

        # === STEP 3: Free fallback — Google dork + SMTP verify ===
        hr_email_count = sum(1 for _, t, _ in new_emails if t == "hr")
        if hr_email_count == 0 and browser_pool:
            discovered = await self._email_discovery.discover_emails(
                lead.company_name, domain, browser_pool
            )
            for email, etype, source in discovered:
                if email.lower() not in existing_emails and _is_valid_email(email):
                    new_emails.append((email, etype, source))
                    existing_emails.add(email.lower())

        # === STEP 4: Google search for phone + email ===
        if browser_pool:
            location = lead.location or "India"
            g_phones, g_emails = await self._google_search_contacts(
                lead.company_name, domain, location, browser_pool
            )
            for phone, ptype in g_phones:
                cleaned = re.sub(r"[\s\-\(\).]", "", phone)
                if cleaned not in existing_phones and _is_valid_phone(phone):
                    new_phones.append((phone, ptype))
                    existing_phones.add(cleaned)
            for email, etype in g_emails:
                if email.lower() not in existing_emails and _is_valid_email(email):
                    new_emails.append((email, etype, "google"))
                    existing_emails.add(email.lower())

        # === STEP 5: Contact page scraping ===
        website = lead.website
        if website and browser_pool and not new_phones:
            page_texts = await self._scrape_contact_pages(website, browser_pool)
            for text in page_texts:
                for email, etype in extract_emails_from_text(text):
                    if email.lower() not in existing_emails and _is_valid_email(email):
                        new_emails.append((email, etype, "scraped"))
                        existing_emails.add(email.lower())
                for phone, ptype in extract_phones_from_text(text):
                    cleaned = re.sub(r"[\s\-\(\).]", "", phone)
                    if cleaned not in existing_phones and _is_valid_phone(phone):
                        new_phones.append((phone, ptype))
                        existing_phones.add(cleaned)

        # === STEP 6: Store ===
        for email, etype, source in new_emails:
            db.add(LeadEmail(
                lead_id=lead.id, email=email, email_type=etype, source=source, verified=False,
            ))
        for phone, ptype in new_phones:
            db.add(LeadPhone(lead_id=lead.id, phone=phone, phone_type=ptype))

        if new_emails or new_phones:
            await db.flush()
            logger.info(
                "lead_enriched", lead_id=str(lead.id), company=lead.company_name,
                new_emails=len(new_emails), new_phones=len(new_phones),
            )

    async def _google_search_contacts(
        self, company_name: str, domain: str | None, location: str, browser_pool: BrowserPool,
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
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

            queries = [f"{company_name} {location} phone number contact hr email"]
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

                    for phone in PHONE_RE.findall(combined):
                        cleaned = re.sub(r"[\s\-\(\).]", "", phone)
                        if cleaned in phone_seen or not _is_valid_phone(phone):
                            continue
                        phone_seen.add(cleaned)
                        ptype = "toll_free" if re.sub(r"\D", "", cleaned).startswith("1800") else "main"
                        phones.append((phone.strip(), ptype))

                    for email in EMAIL_RE.findall(combined):
                        email_lower = email.lower()
                        if email_lower in email_seen or not _is_valid_email(email):
                            continue
                        email_domain = email_lower.split("@")[1]
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

    async def _scrape_contact_pages(self, website: str, browser_pool: BrowserPool) -> list[str]:
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
            logger.warning("enrichment_scrape_failed", website=website)
        finally:
            await browser_pool.release(ctx)
        return texts
