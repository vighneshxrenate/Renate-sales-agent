import asyncio

import aiohttp
import structlog

from app.config import settings

logger = structlog.get_logger()

APIFY_BASE = "https://api.apify.com/v2"

ACTOR_IDS = {
    "linkedin": "bebity~linkedin-jobs-scraper",
    "naukri": "bebity~naukri-scraper",
}

POLL_INTERVAL = 10
MAX_WAIT = 300


class ApifyClient:
    def __init__(self) -> None:
        self._token = settings.apify_api_key

    @property
    def available(self) -> bool:
        return bool(self._token)

    async def run_actor(
        self, source: str, keywords: str, location: str, max_results: int = 50
    ) -> list[dict]:
        actor_id = ACTOR_IDS.get(source)
        if not actor_id:
            raise ValueError(f"No Apify actor configured for source: {source}")

        input_data = {
            "searchTerms": [keywords],
            "location": location,
            "maxResults": max_results,
        }

        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            # Start the actor run
            async with session.post(
                f"{APIFY_BASE}/acts/{actor_id}/runs",
                json=input_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 201:
                    body = await resp.text()
                    raise RuntimeError(f"Apify start failed ({resp.status}): {body}")
                run_data = await resp.json()
                run_id = run_data["data"]["id"]

            logger.info("apify_actor_started", actor=actor_id, run_id=run_id)

            # Poll for completion
            elapsed = 0
            while elapsed < MAX_WAIT:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL

                async with session.get(
                    f"{APIFY_BASE}/actor-runs/{run_id}",
                    headers=headers,
                ) as resp:
                    status_data = await resp.json()
                    status = status_data["data"]["status"]

                    if status == "SUCCEEDED":
                        break
                    if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                        raise RuntimeError(f"Apify run {status}: {run_id}")
            else:
                raise TimeoutError(f"Apify run timed out after {MAX_WAIT}s")

            # Fetch results
            dataset_id = status_data["data"]["defaultDatasetId"]
            async with session.get(
                f"{APIFY_BASE}/datasets/{dataset_id}/items",
                headers=headers,
                params={"format": "json"},
            ) as resp:
                results = await resp.json()

            logger.info("apify_results_fetched", count=len(results))
            return results
