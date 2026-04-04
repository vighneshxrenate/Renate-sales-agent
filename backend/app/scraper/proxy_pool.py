import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import async_session
from app.models.proxy import Proxy

logger = structlog.get_logger()

COOLDOWN_MINUTES = 10
MAX_CONSECUTIVE_FAILURES = 3


@dataclass
class ProxyConfig:
    server: str
    username: str | None = None
    password: str | None = None

    def to_playwright(self) -> dict:
        d: dict = {"server": self.server}
        if self.username:
            d["username"] = self.username
        if self.password:
            d["password"] = self.password
        return d


class ProxyPool:
    def __init__(self) -> None:
        self._proxies: list[dict] = []

    async def initialize(self) -> None:
        async with async_session() as db:
            result = await db.execute(select(Proxy).where(Proxy.is_active == True))
            db_proxies = result.scalars().all()
            self._proxies = [
                {
                    "id": str(p.id),
                    "server": f"{p.protocol}://{p.host}:{p.port}",
                    "username": p.username,
                    "password": p.password,
                    "provider": p.provider,
                    "fail_count": p.fail_count,
                    "success_count": p.success_count,
                    "cooldown_until": p.cooldown_until,
                    "last_used_at": p.last_used_at,
                }
                for p in db_proxies
            ]

        if settings.proxy_list:
            for i, entry in enumerate(settings.proxy_list.split(",")):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split(":")
                if len(parts) != 4:
                    logger.warning("invalid_proxy_entry", entry=entry)
                    continue
                host, port, username, password = parts
                self._proxies.append({
                    "id": f"proxy-cheap-{i}",
                    "server": f"http://{host}:{port}",
                    "username": username,
                    "password": password,
                    "provider": "proxy-cheap",
                    "fail_count": 0,
                    "success_count": 0,
                    "cooldown_until": None,
                    "last_used_at": None,
                })

        logger.info("proxy_pool_initialized", count=len(self._proxies))

    def get_proxy(self, source: str = "default", sticky_session: str | None = None) -> ProxyConfig | None:
        if not self._proxies:
            return None

        now = datetime.now(timezone.utc)
        available = [
            p for p in self._proxies
            if not p["cooldown_until"] or p["cooldown_until"] < now
        ]

        if not available:
            logger.warning("no_proxies_available", source=source)
            return None

        if source == "naukri":
            indian = [p for p in available if p.get("provider") in ("proxy-cheap", "indian_residential")]
            if indian:
                available = indian

        available.sort(key=lambda p: p["fail_count"])
        proxy = available[0] if len(available) < 3 else random.choice(available[:3])

        username = proxy["username"] or ""
        if sticky_session and proxy.get("provider") == "smartproxy":
            username = f"{username}-session-{sticky_session}"

        proxy["last_used_at"] = now
        return ProxyConfig(
            server=proxy["server"],
            username=username,
            password=proxy["password"],
        )

    async def report_success(self, proxy_server: str, response_ms: int) -> None:
        for p in self._proxies:
            if p["server"] == proxy_server:
                p["fail_count"] = 0
                p["success_count"] = p.get("success_count", 0) + 1
                break

    async def report_failure(self, proxy_server: str) -> None:
        for p in self._proxies:
            if p["server"] == proxy_server:
                p["fail_count"] = p.get("fail_count", 0) + 1
                if p["fail_count"] >= MAX_CONSECUTIVE_FAILURES:
                    p["cooldown_until"] = datetime.now(timezone.utc) + timedelta(minutes=COOLDOWN_MINUTES)
                    logger.warning("proxy_cooldown", server=proxy_server, minutes=COOLDOWN_MINUTES)
                break

    async def health_check(self) -> None:
        logger.info("proxy_health_check_start", total=len(self._proxies))
        for proxy_data in self._proxies:
            proxy = ProxyConfig(
                server=proxy_data["server"],
                username=proxy_data.get("username"),
                password=proxy_data.get("password"),
            )
            try:
                async with aiohttp.ClientSession() as session:
                    proxy_url = proxy.server
                    if proxy.username:
                        proto, rest = proxy_url.split("://", 1)
                        proxy_url = f"{proto}://{proxy.username}:{proxy.password}@{rest}"
                    async with session.get(
                        "https://httpbin.org/ip",
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status == 200:
                            proxy_data["fail_count"] = 0
                        else:
                            proxy_data["fail_count"] = proxy_data.get("fail_count", 0) + 1
            except Exception:
                proxy_data["fail_count"] = proxy_data.get("fail_count", 0) + 1

        logger.info("proxy_health_check_done")
