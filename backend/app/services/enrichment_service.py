from urllib.parse import urljoin

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadEmail, LeadPhone
from app.scraper.browser_pool import BrowserPool
from app.scraper.proxy_pool import ProxyPool
from app.services.apollo_client import ApolloClient
from app.utils.dns_discovery import verify_domain_has_mx
from app.utils.email_patterns import (
    extract_domain,
    extract_emails_from_text,
    extract_phones_from_text,
    generate_email_candidates,
)

logger = structlog.get_logger()

CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us"]


class EnrichmentService:
    def __init__(self) -> None:
        self._apollo = ApolloClient()

    async def enrich_lead(
        self,
        lead: Lead,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
        db: AsyncSession,
    ) -> None:
        existing_emails = {e.email.lower() for e in lead.emails} if lead.emails else set()
        existing_phones = {p.phone for p in lead.phones} if lead.phones else set()

        new_emails: list[tuple[str, str, str]] = []  # (email, type, source)
        new_phones: list[tuple[str, str]] = []

        domain = extract_domain(lead.website)

        # 1. Scrape contact/about pages for emails and phones
        if lead.website:
            page_texts = await self._scrape_contact_pages(lead.website, browser_pool, proxy_pool)
            for text in page_texts:
                for email, etype in extract_emails_from_text(text):
                    if email.lower() not in existing_emails:
                        new_emails.append((email, etype, "scraped"))
                        existing_emails.add(email.lower())
                for phone, ptype in extract_phones_from_text(text):
                    if phone not in existing_phones:
                        new_phones.append((phone, ptype))
                        existing_phones.add(phone)

        # 2. Generate and verify email pattern candidates
        if domain:
            has_mx = await verify_domain_has_mx(domain)
            if has_mx:
                candidates = generate_email_candidates(domain)
                for email, etype in candidates:
                    if email.lower() not in existing_emails:
                        new_emails.append((email, etype, "pattern_guess"))
                        existing_emails.add(email.lower())

        # 3. Apollo.io fallback — if we found fewer than 2 emails from scraping
        scraped_count = sum(1 for _, _, src in new_emails if src == "scraped")
        if scraped_count < 2 and domain and self._apollo.available:
            apollo_emails, apollo_phones = await self._enrich_via_apollo(domain, existing_emails)
            for email, etype in apollo_emails:
                if email.lower() not in existing_emails:
                    new_emails.append((email, etype, "apollo"))
                    existing_emails.add(email.lower())
            for phone, ptype in apollo_phones:
                if phone not in existing_phones:
                    new_phones.append((phone, ptype))
                    existing_phones.add(phone)

        # 4. Store discovered contacts
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
                new_emails=len(new_emails),
                new_phones=len(new_phones),
            )

    async def _enrich_via_apollo(
        self, domain: str, existing_emails: set[str]
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        emails: list[tuple[str, str]] = []
        phones: list[tuple[str, str]] = []

        # Search for HR/recruiting contacts at the company
        contacts = await self._apollo.search_contacts(domain, limit=5)
        for person in contacts:
            email = person.get("email")
            if email and email.lower() not in existing_emails:
                title = (person.get("title") or "").lower()
                if any(kw in title for kw in ("hr", "recruit", "talent", "hiring", "people")):
                    etype = "hr"
                else:
                    etype = "personal"
                emails.append((email, etype))

            phone = person.get("phone_number") or person.get("sanitized_phone")
            if phone:
                phones.append((phone, "main"))

        # Also try company enrichment for generic emails
        org = await self._apollo.enrich_company(domain)
        if org:
            for phone_entry in org.get("phone_numbers", []):
                number = phone_entry.get("sanitized_number") or phone_entry.get("number")
                if number:
                    phones.append((number, "main"))

        logger.info("apollo_enrichment_done", domain=domain, emails=len(emails), phones=len(phones))
        return emails, phones

    async def _scrape_contact_pages(
        self, website: str, browser_pool: BrowserPool, proxy_pool: ProxyPool
    ) -> list[str]:
        if not website.startswith("http"):
            website = f"https://{website}"

        texts: list[str] = []
        proxy = proxy_pool.get_proxy(source="career_page")
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="minimal", proxy=proxy_dict)

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
