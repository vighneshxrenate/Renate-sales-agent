import asyncio
import time
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update

from app.config import settings
from app.db.engine import async_session
from app.models.proxy import Proxy

logger = structlog.get_logger()

COOLDOWN_SECONDS = 60
MAX_FAIL_COUNT = 5


class ProxyEntry:
    __slots__ = ("url", "proxy_id", "fail_count", "success_count", "cooldown_until", "last_used")

    def __init__(self, url: str, proxy_id: str | None = None):
        self.url = url
        self.proxy_id = proxy_id
        self.fail_count = 0
        self.success_count = 0
        self.cooldown_until: float = 0
        self.last_used: float = 0


class ProxyPool:
    def __init__(self):
        self._proxies: list[ProxyEntry] = []
        self._lock = asyncio.Lock()
        self._index = 0

    async def initialize(self) -> None:
        await self._load_from_db()
        self._add_gateway_proxy()
        logger.info("proxy_pool.initialized", count=len(self._proxies))

    def _add_gateway_proxy(self) -> None:
        if not settings.proxy_host:
            return
        auth = ""
        if settings.proxy_username:
            auth = f"{settings.proxy_username}:{settings.proxy_password}@"
        url = f"http://{auth}{settings.proxy_host}:{settings.proxy_port}"
        self._proxies.append(ProxyEntry(url=url))

    async def _load_from_db(self) -> None:
        async with async_session() as db:
            result = await db.execute(
                select(Proxy).where(Proxy.is_active == True)  # noqa: E712
            )
            for p in result.scalars().all():
                auth = ""
                if p.username:
                    auth = f"{p.username}:{p.password}@"
                url = f"{p.protocol}://{auth}{p.host}:{p.port}"
                entry = ProxyEntry(url=url, proxy_id=str(p.id))
                entry.fail_count = p.fail_count
                entry.success_count = p.success_count
                if p.cooldown_until:
                    entry.cooldown_until = p.cooldown_until.timestamp()
                self._proxies.append(entry)

    async def get_proxy(self) -> ProxyEntry | None:
        if not self._proxies:
            return None
        async with self._lock:
            now = time.time()
            attempts = len(self._proxies)
            for _ in range(attempts):
                entry = self._proxies[self._index % len(self._proxies)]
                self._index += 1
                if entry.cooldown_until <= now and entry.fail_count < MAX_FAIL_COUNT:
                    entry.last_used = now
                    return entry
            return None

    async def report_success(self, entry: ProxyEntry, response_ms: int = 0) -> None:
        entry.success_count += 1
        entry.fail_count = 0
        if entry.proxy_id:
            await self._update_db(entry, response_ms)

    async def report_failure(self, entry: ProxyEntry) -> None:
        entry.fail_count += 1
        if entry.fail_count >= 3:
            entry.cooldown_until = time.time() + COOLDOWN_SECONDS
        logger.warning("proxy.failure", url=entry.url, fail_count=entry.fail_count)
        if entry.proxy_id:
            await self._update_db(entry)

    async def _update_db(self, entry: ProxyEntry, response_ms: int | None = None) -> None:
        if not entry.proxy_id:
            return
        try:
            async with async_session() as db:
                values: dict = {
                    "fail_count": entry.fail_count,
                    "success_count": entry.success_count,
                    "last_used_at": datetime.now(timezone.utc),
                }
                if entry.cooldown_until > 0:
                    values["cooldown_until"] = datetime.fromtimestamp(
                        entry.cooldown_until, tz=timezone.utc
                    )
                if response_ms:
                    values["avg_response_ms"] = response_ms
                await db.execute(
                    update(Proxy).where(Proxy.id == entry.proxy_id).values(**values)
                )
                await db.commit()
        except Exception:
            logger.exception("proxy.db_update_failed")

    async def health_check(self) -> dict:
        total = len(self._proxies)
        now = time.time()
        available = sum(
            1 for p in self._proxies
            if p.cooldown_until <= now and p.fail_count < MAX_FAIL_COUNT
        )
        return {"total": total, "available": available, "cooldown": total - available}

    @property
    def size(self) -> int:
        return len(self._proxies)
