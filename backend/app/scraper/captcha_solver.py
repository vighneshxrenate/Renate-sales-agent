import asyncio

import aiohttp
import structlog
from playwright.async_api import Page

from app.config import settings

logger = structlog.get_logger()

TWOCAPTCHA_API = "https://2captcha.com/in.php"
TWOCAPTCHA_RESULT = "https://2captcha.com/res.php"
POLL_INTERVAL = 5
MAX_WAIT = 120


class CaptchaSolver:
    def __init__(self) -> None:
        self._api_key = settings.captcha_api_key

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def _submit(self, params: dict) -> str:
        params["key"] = self._api_key
        params["json"] = "1"
        async with aiohttp.ClientSession() as session:
            async with session.post(TWOCAPTCHA_API, data=params) as resp:
                data = await resp.json()
                if data.get("status") != 1:
                    raise RuntimeError(f"2captcha submit failed: {data}")
                return data["request"]

    async def _poll_result(self, task_id: str) -> str:
        params = {"key": self._api_key, "action": "get", "id": task_id, "json": "1"}
        elapsed = 0
        async with aiohttp.ClientSession() as session:
            while elapsed < MAX_WAIT:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                async with session.get(TWOCAPTCHA_RESULT, params=params) as resp:
                    data = await resp.json()
                    if data.get("status") == 1:
                        return data["request"]
                    if data.get("request") != "CAPCHA_NOT_READY":
                        raise RuntimeError(f"2captcha error: {data}")
        raise TimeoutError("CAPTCHA solve timed out")

    async def solve_recaptcha(self, site_key: str, page_url: str) -> str:
        logger.info("solving_recaptcha", url=page_url)
        task_id = await self._submit({
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
        })
        return await self._poll_result(task_id)

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        logger.info("solving_hcaptcha", url=page_url)
        task_id = await self._submit({
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
        })
        return await self._poll_result(task_id)

    async def inject_solution(self, page: Page, token: str) -> None:
        await page.evaluate(f"""
            document.getElementById('g-recaptcha-response').innerHTML = '{token}';
            if (typeof ___grecaptcha_cfg !== 'undefined') {{
                Object.entries(___grecaptcha_cfg.clients).forEach(([k, v]) => {{
                    const callback = Object.values(v).find(x => x && x.callback);
                    if (callback) callback.callback('{token}');
                }});
            }}
        """)
