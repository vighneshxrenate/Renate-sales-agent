import asyncio
import random
import re
from urllib.parse import quote_plus

import aiohttp
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
    ("hr", "hr"), ("recruitment", "hr"), ("careers", "hr"),
    ("hiring", "hr"), ("talent", "hr"), ("jobs", "hr"),
    ("people", "hr"), ("humanresources", "hr"),
    ("placement", "hr"), ("joinus", "hr"),
]

GOOGLE_CONSENT_COOKIES = [
    {"name": "CONSENT", "value": "YES+cb.20231008-07-p0.en+FX+410", "domain": ".google.co.in", "path": "/"},
]


def _is_valid_discovered_email(email: str, domain: str | None) -> bool:
    email_lower = email.lower()
    local = email_lower.split("@")[0]
    email_domain = email_lower.split("@")[1]

    if email_domain in JUNK_DOMAINS:
        return False
    if len(local) < 3:
        return False
    if "%" in email or "+" in email or email.startswith(".") or "u003e" in email_lower:
        return False
    if local in ("name", "email", "your", "user", "test", "info", "example", "abc"):
        return False

    is_company = domain and domain in email_domain
    is_personal = email_domain in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "rediffmail.com")
    return is_company or is_personal


class EmailDiscoveryService:
    """Free email discovery via Google/DuckDuckGo dorking + SMTP verification."""

    async def discover_emails(
        self, company_name: str, domain: str | None, browser_pool: BrowserPool,
    ) -> list[tuple[str, str, str]]:
        results: list[tuple[str, str, str]] = []
        seen: set[str] = set()

        # 1. SMTP-verify functional mailboxes
        if domain:
            has_mx = await verify_domain_has_mx(domain)
            if has_mx:
                verified = await self._check_functional_mailboxes(domain)
                for email, etype in verified:
                    if email.lower() not in seen:
                        results.append((email, etype, "smtp_verified"))
                        seen.add(email.lower())

        # 2. DuckDuckGo dork (no CAPTCHAs, always works)
        if browser_pool:
            ddg_emails = await self._duckduckgo_dork_emails(company_name, domain, browser_pool)
            for email, etype in ddg_emails:
                if email.lower() not in seen and _is_valid_discovered_email(email, domain):
                    results.append((email, etype, "duckduckgo"))
                    seen.add(email.lower())

        # 3. Google dork fallback (may get blocked)
        if len(results) < 2 and browser_pool:
            google_emails = await self._google_dork_emails(company_name, domain, browser_pool)
            for email, etype in google_emails:
                if email.lower() not in seen and _is_valid_discovered_email(email, domain):
                    results.append((email, etype, "google_dork"))
                    seen.add(email.lower())

        if results:
            logger.info("email_discovery_done", company=company_name, domain=domain, found=len(results))

        return results

    async def _check_functional_mailboxes(self, domain: str) -> list[tuple[str, str]]:
        verified: list[tuple[str, str]] = []

        # Check catch-all first
        random_addr = f"xyznonexistent{random.randint(10000,99999)}@{domain}"
        is_catchall = await verify_email_smtp(random_addr)
        if is_catchall:
            return []

        # Check all in parallel
        async def check_one(prefix: str, etype: str) -> tuple[str, str] | None:
            email = f"{prefix}@{domain}"
            try:
                exists = await verify_email_smtp(email)
                if exists:
                    return (email, etype)
            except Exception:
                pass
            return None

        tasks = [check_one(prefix, etype) for prefix, etype in FUNCTIONAL_MAILBOXES]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r:
                verified.append(r)

        return verified

    async def _duckduckgo_dork_emails(
        self, company_name: str, domain: str | None, browser_pool: BrowserPool,
    ) -> list[tuple[str, str]]:
        """DuckDuckGo HTML search — no CAPTCHAs, always works."""
        emails: list[tuple[str, str]] = []
        seen: set[str] = set()

        queries = []
        if domain:
            queries.append(f'"@{domain}" recruiter OR hr OR hiring OR talent')
        queries.append(f'"{company_name}" India recruiter email hr contact')

        try:
            async with aiohttp.ClientSession() as session:
                for query in queries[:2]:
                    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                    async with session.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        html = await resp.text()

                    for email in EMAIL_RE.findall(html):
                        email_lower = email.lower()
                        if email_lower in seen or not _is_valid_discovered_email(email, domain):
                            continue
                        seen.add(email_lower)
                        local = email_lower.split("@")[0]
                        hr_kw = ("hr", "recruit", "talent", "hiring", "career", "people")
                        etype = "hr" if any(kw in local for kw in hr_kw) else "personal"
                        emails.append((email, etype))

                    await asyncio.sleep(1)
        except Exception:
            logger.warning("duckduckgo_dork_failed", company=company_name)

        return emails[:10]

    async def _google_dork_emails(
        self, company_name: str, domain: str | None, browser_pool: BrowserPool,
    ) -> list[tuple[str, str]]:
        emails: list[tuple[str, str]] = []
        seen: set[str] = set()

        queries = []
        if domain:
            queries.append(f'"@{domain}" recruiter OR hr OR hiring OR talent')
        queries.append(f'site:naukri.com "{company_name}" email contact')

        ctx = await browser_pool.acquire(stealth_level="minimal", proxy=None)
        try:
            page = await ctx.context.new_page()
            await ctx.context.add_cookies(GOOGLE_CONSENT_COOKIES)
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            for query in queries[:2]:
                try:
                    url = f"https://www.google.co.in/search?q={quote_plus(query)}&num=20&hl=en"
                    await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                    await page.wait_for_timeout(2000)

                    text = await page.inner_text("body")
                    if "unusual traffic" in text.lower():
                        break

                    html = await page.content()
                    for email in EMAIL_RE.findall(html + " " + text):
                        email_lower = email.lower()
                        if email_lower in seen or not _is_valid_discovered_email(email, domain):
                            continue
                        seen.add(email_lower)
                        local = email_lower.split("@")[0]
                        hr_kw = ("hr", "recruit", "talent", "hiring", "career", "people")
                        etype = "hr" if any(kw in local for kw in hr_kw) else "personal"
                        emails.append((email, etype))

                    await asyncio.sleep(random.uniform(2, 4))
                except Exception:
                    continue

            await page.close()
        except Exception:
            logger.warning("google_dork_failed", company=company_name)
        finally:
            await browser_pool.release(ctx)

        return emails[:10]
