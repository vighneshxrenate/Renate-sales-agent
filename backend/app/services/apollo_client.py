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
    async def search_hr_contacts(
        self, company_name: str, limit: int = 5
    ) -> list[dict]:
        """Search for HR/recruiting contacts. Requires paid plan for API access."""
        if not self.available:
            return []

        titles = [
            "HR", "Human Resources", "Talent Acquisition",
            "Recruiter", "Hiring Manager", "People Operations",
            "Recruitment", "HR Manager", "HR Director",
        ]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{APOLLO_BASE}/mixed_people/search",
                    headers={"Content-Type": "application/json", "X-Api-Key": self._api_key},
                    json={
                        "q_organization_name": company_name,
                        "person_titles": titles,
                        "per_page": limit,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        data = await resp.json()
                        if "not accessible" in data.get("error", ""):
                            logger.info("apollo_people_search_requires_paid_plan")
                            return []
                        logger.warning("apollo_search_failed", company=company_name, status=resp.status)
                        return []
                    data = await resp.json()
                    return data.get("people", [])
        except Exception:
            logger.warning("apollo_search_error", company=company_name)
            return []

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10), reraise=True)
    async def enrich_company(self, company_name: str) -> dict | None:
        """Get company info including phone numbers. Works on free plan."""
        if not self.available:
            return None

        try:
            # First try domain lookup by company name
            async with aiohttp.ClientSession() as session:
                # Search for org to get domain
                async with session.post(
                    f"{APOLLO_BASE}/mixed_companies/search",
                    headers={"Content-Type": "application/json", "X-Api-Key": self._api_key},
                    json={"q_organization_name": company_name, "per_page": 1},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        orgs = data.get("organizations", [])
                        if orgs:
                            domain = orgs[0].get("primary_domain")
                            if domain:
                                return await self._enrich_by_domain(domain)

                # Fallback: try common domain patterns
                return None
        except Exception:
            return None

    async def _enrich_by_domain(self, domain: str) -> dict | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{APOLLO_BASE}/organizations/enrich",
                    headers={"Content-Type": "application/json", "X-Api-Key": self._api_key},
                    json={"domain": domain},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data.get("organization")
        except Exception:
            return None
