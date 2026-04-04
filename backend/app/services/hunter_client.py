import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = structlog.get_logger()

HUNTER_BASE = "https://api.hunter.io/v2"


class HunterClient:
    def __init__(self) -> None:
        self._api_key = settings.hunter_api_key

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10), reraise=True)
    async def domain_search(self, domain: str, limit: int = 10) -> list[dict]:
        if not self.available:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{HUNTER_BASE}/domain-search",
                    params={
                        "domain": domain,
                        "api_key": self._api_key,
                        "limit": limit,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        logger.debug("hunter_domain_search_failed", domain=domain, status=resp.status)
                        return []
                    data = await resp.json()
                    return data.get("data", {}).get("emails", [])
        except Exception:
            logger.debug("hunter_domain_search_error", domain=domain)
            return []

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10), reraise=True)
    async def company_search(self, company_name: str, limit: int = 10, department: str | None = None) -> tuple[str | None, list[dict]]:
        """Search by company name. Returns (domain, emails)."""
        if not self.available:
            return None, []

        try:
            params = {
                "company": company_name,
                "api_key": self._api_key,
                "limit": limit,
            }
            if department:
                params["department"] = department

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{HUNTER_BASE}/domain-search",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        logger.debug("hunter_company_search_failed", company=company_name, status=resp.status)
                        return None, []
                    data = await resp.json()
                    result = data.get("data", {})
                    domain = result.get("domain")
                    emails = result.get("emails", [])
                    return domain, emails
        except Exception:
            logger.debug("hunter_company_search_error", company=company_name)
            return None, []

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10), reraise=True)
    async def find_email(self, first_name: str, last_name: str, domain: str) -> str | None:
        if not self.available:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{HUNTER_BASE}/email-finder",
                    params={
                        "domain": domain,
                        "first_name": first_name,
                        "last_name": last_name,
                        "api_key": self._api_key,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data.get("data", {}).get("email")
        except Exception:
            return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10), reraise=True)
    async def verify_email(self, email: str) -> dict | None:
        if not self.available:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{HUNTER_BASE}/email-verifier",
                    params={"email": email, "api_key": self._api_key},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data.get("data")
        except Exception:
            return None
