import asyncio
import random
import re
from urllib.parse import quote_plus

import structlog
from playwright.async_api import BrowserContext

from app.scraper.browser_pool import BrowserPool
from app.utils.dns_discovery import verify_email_smtp, verify_domain_has_mx

logger = structlog.get_logger()

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

JUNK_DOMAINS = {
    "example.com", "test.com", "sentry.io", "googleapis.com", "w3.org",
    "schema.org", "cloudflare.com", "gstatic.com", "google.com",
    "facebook.com", "twitter.com", "youtube.com", "github.com",
    "wikipedia.org", "mozilla.org", "apple.com", "microsoft.com",
}

FUNCTIONAL_MAILBOXES = [
    ("hr", "hr"),
    ("recruitment", "hr"),
    ("careers", "hr"),
    ("hiring", "hr"),
    ("talent", "hr"),
    ("jobs", "hr"),
    ("people", "hr"),
    ("humanresources", "hr"),
]

GOOGLE_CONSENT_COOKIES = [
    {"name": "CONSENT", "value": "YES+cb.20231008-07-p0.en+FX+410", "domain": ".google.co.in", "path": "/"},
]


class EmailDiscoveryService:
    """Free email discovery via Google dorking + SMTP verification."""

    async def discover_emails(
        self,
        company_name: str,
        domain: str | None,
        browser_pool: BrowserPool,
    ) -> list[tuple[str, str, str]]:
        """Returns list of (email, type, source)."""
        results: list[tuple[str, str, str]] = []
        seen: set[str] = set()

        # 1. SMTP-verify functional mailboxes (hr@, careers@, etc.)
        if domain:
            has_mx = await verify_domain_has_mx(domain)
            if has_mx:
                verified = await self._check_functional_mailboxes(domain)
                for email, etype in verified:
                    if email.lower() not in seen:
                        results.append((email, etype, "smtp_verified"))
                        seen.add(email.lower())

        # 2. Google dork for leaked recruiter emails
        if browser_pool:
            dorked = await self._google_dork_emails(company_name, domain, browser_pool)
            for email, etype in dorked:
                if email.lower() not in seen:
                    results.append((email, etype, "google_dork"))
                    seen.add(email.lower())

        if results:
            logger.info(
                "email_discovery_done",
                company=company_name,
                domain=domain,
                found=len(results),
            )

        return results

    async def _check_functional_mailboxes(self, domain: str) -> list[tuple[str, str]]:
        """Check if common HR mailboxes exist via SMTP."""
        verified: list[tuple[str, str]] = []

        # First check if the domain is a catch-all (accepts any address)
        random_addr = f"xyznonexistent{random.randint(10000,99999)}@{domain}"
        is_catchall = await verify_email_smtp(random_addr)
        if is_catchall:
            logger.warning("smtp_catchall_domain", domain=domain)
            return []  # Can't verify individual addresses

        tasks = []
        for prefix, etype in FUNCTIONAL_MAILBOXES:
            email = f"{prefix}@{domain}"
            tasks.append((email, etype, verify_email_smtp(email)))

        for email, etype, coro in tasks:
            try:
                exists = await coro
                if exists:
                    verified.append((email, etype))
                    logger.warning("functional_mailbox_verified", email=email)
            except Exception:
                pass

        return verified

    async def _google_dork_emails(
        self,
        company_name: str,
        domain: str | None,
        browser_pool: BrowserPool,
    ) -> list[tuple[str, str]]:
        """Search Google for recruiter/HR emails mentioned on web pages."""
        emails: list[tuple[str, str]] = []
        seen: set[str] = set()

        queries = []
        if domain:
            queries.append(f'"@{domain}" recruiter OR hr OR hiring OR talent')
            queries.append(f'site:naukri.com "{company_name}" "@{domain}"')
        queries.append(f'"{company_name}" India recruiter email contact')

        ctx = await browser_pool.acquire(stealth_level="minimal", proxy=None)
        try:
            page = await ctx.context.new_page()
            await ctx.context.add_cookies(GOOGLE_CONSENT_COOKIES)
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            for query in queries[:2]:  # Limit to 2 queries to avoid captcha
                try:
                    url = f"https://www.google.co.in/search?q={quote_plus(query)}&num=20&hl=en"
                    await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                    await page.wait_for_timeout(2000)

                    text = await page.inner_text("body")
                    if "unusual traffic" in text.lower():
                        logger.warning("google_dork_blocked")
                        break

                    html = await page.content()
                    found = EMAIL_RE.findall(html + " " + text)

                    for email in found:
                        email_lower = email.lower()
                        email_domain = email_lower.split("@")[1]

                        if email_domain in JUNK_DOMAINS:
                            continue
                        if email_lower in seen:
                            continue

                        # Only keep emails from the company domain or personal emails
                        # Skip junk emails
                        local_part = email_lower.split("@")[0]
                        if ("%" in email or "+" in email or email.startswith(".")
                                or "u003e" in email_lower or len(local_part) < 3
                                or local_part in ("name", "email", "your", "user", "test", "info")):
                            continue

                        is_company = domain and domain in email_domain
                        is_personal = email_domain in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "rediffmail.com")

                        if not is_company and not is_personal:
                            continue

                        seen.add(email_lower)
                        local_part = email_lower.split("@")[0]
                        hr_keywords = ("hr", "recruit", "talent", "hiring", "career", "people")
                        etype = "hr" if any(kw in local_part for kw in hr_keywords) else "personal"
                        emails.append((email, etype))

                    await asyncio.sleep(random.uniform(2, 4))

                except Exception:
                    logger.warning("google_dork_query_failed", query=query[:50])
                    continue

            await page.close()
        except Exception:
            logger.warning("google_dork_failed", company=company_name)
        finally:
            await browser_pool.release(ctx)

        return emails[:10]
