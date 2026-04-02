import aiohttp
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = structlog.get_logger()

APOLLO_BASE = "https://api.apollo.io/v1"


class ApolloClient:
    def __init__(self) -> None:
        self._api_key = settings.apollo_api_key

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10), reraise=True)
    async def enrich_company(self, domain: str) -> dict | None:
        """Enrich company data by domain. Returns company info including emails."""
        if not self.available:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{APOLLO_BASE}/organizations/enrich",
                    json={"api_key": self._api_key, "domain": domain},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        logger.debug("apollo_enrich_failed", domain=domain, status=resp.status)
                        return None
                    data = await resp.json()
                    return data.get("organization")
        except Exception:
            logger.debug("apollo_enrich_error", domain=domain)
            return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10), reraise=True)
    async def search_contacts(
        self, domain: str, titles: list[str] | None = None, limit: int = 5
    ) -> list[dict]:
        """Search for contacts at a company by domain. Returns people with emails/phones."""
        if not self.available:
            return []

        titles = titles or ["HR", "Human Resources", "Talent Acquisition", "Recruiter", "Hiring Manager"]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{APOLLO_BASE}/mixed_people/search",
                    json={
                        "api_key": self._api_key,
                        "q_organization_domains": domain,
                        "person_titles": titles,
                        "per_page": limit,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        logger.debug("apollo_search_failed", domain=domain, status=resp.status)
                        return []
                    data = await resp.json()
                    return data.get("people", [])
        except Exception:
            logger.debug("apollo_search_error", domain=domain)
            return []

    async def find_email(self, first_name: str, last_name: str, domain: str) -> str | None:
        """Find a specific person's email at a company."""
        if not self.available:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{APOLLO_BASE}/people/match",
                    json={
                        "api_key": self._api_key,
                        "first_name": first_name,
                        "last_name": last_name,
                        "organization_domain": domain,
                        "reveal_personal_emails": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    person = data.get("person", {})
                    return person.get("email")
        except Exception:
            return None
