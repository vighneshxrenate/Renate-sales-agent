import asyncio

import httpx
import structlog

logger = structlog.get_logger()

TWOCAPTCHA_IN = "https://2captcha.com/in.php"
TWOCAPTCHA_RES = "https://2captcha.com/res.php"
POLL_INTERVAL = 5
MAX_WAIT = 120


class CaptchaSolver:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30) if api_key else None

    async def detect_captcha(self, page) -> str | None:
        recaptcha = await page.query_selector("iframe[src*='recaptcha']")
        if recaptcha:
            return "recaptcha"
        hcaptcha = await page.query_selector("iframe[src*='hcaptcha']")
        if hcaptcha:
            return "hcaptcha"
        return None

    async def solve_recaptcha(self, page, site_key: str, page_url: str) -> str | None:
        if not self._client:
            logger.warning("captcha.no_api_key")
            return None

        resp = await self._client.post(TWOCAPTCHA_IN, data={
            "key": self._api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1,
        })
        result = resp.json()
        if result.get("status") != 1:
            logger.error("captcha.submit_failed", error=result.get("request"))
            return None

        task_id = result["request"]
        return await self._poll_result(task_id)

    async def solve_hcaptcha(self, page, site_key: str, page_url: str) -> str | None:
        if not self._client:
            logger.warning("captcha.no_api_key")
            return None

        resp = await self._client.post(TWOCAPTCHA_IN, data={
            "key": self._api_key,
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1,
        })
        result = resp.json()
        if result.get("status") != 1:
            logger.error("captcha.submit_failed", error=result.get("request"))
            return None

        task_id = result["request"]
        return await self._poll_result(task_id)

    async def _poll_result(self, task_id: str) -> str | None:
        elapsed = 0
        while elapsed < MAX_WAIT:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            resp = await self._client.get(TWOCAPTCHA_RES, params={
                "key": self._api_key,
                "action": "get",
                "id": task_id,
                "json": 1,
            })
            result = resp.json()
            if result.get("status") == 1:
                logger.info("captcha.solved", task_id=task_id)
                return result["request"]
            if result.get("request") != "CAPCHA_NOT_READY":
                logger.error("captcha.poll_error", error=result.get("request"))
                return None
        logger.error("captcha.timeout", task_id=task_id)
        return None

    async def solve_if_present(self, page) -> bool:
        captcha_type = await self.detect_captcha(page)
        if not captcha_type:
            return False

        page_url = page.url
        if captcha_type == "recaptcha":
            site_key = await page.evaluate(
                "document.querySelector('[data-sitekey]')?.getAttribute('data-sitekey')"
            )
            if not site_key:
                return False
            token = await self.solve_recaptcha(page, site_key, page_url)
            if token:
                await page.evaluate(
                    f"document.getElementById('g-recaptcha-response').value = '{token}'"
                )
                return True
        elif captcha_type == "hcaptcha":
            site_key = await page.evaluate(
                "document.querySelector('[data-sitekey]')?.getAttribute('data-sitekey')"
            )
            if not site_key:
                return False
            token = await self.solve_hcaptcha(page, site_key, page_url)
            if token:
                await page.evaluate(
                    f"document.querySelector('[name=\"h-captcha-response\"]').value = '{token}'"
                )
                return True
        return False

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
