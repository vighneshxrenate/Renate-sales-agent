from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.scrape_job import ScrapeJob
    from app.scraper.browser_pool import BrowserPool
    from app.scraper.proxy_pool import ProxyPool


@dataclass
class ScraperResult:
    raw_html: str
    url: str
    source: str
    page_number: int = 0
    metadata: dict = field(default_factory=dict)
    structured_leads: list | None = None  # Pre-extracted leads — skips LLM


class AbstractScraper(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    async def scrape(
        self,
        job: "ScrapeJob",
        browser_pool: "BrowserPool",
        proxy_pool: "ProxyPool",
    ) -> AsyncGenerator[ScraperResult, None]: ...


SCRAPERS: dict[str, type[AbstractScraper]] = {}


def register_scraper(cls: type[AbstractScraper]) -> type[AbstractScraper]:
    instance = cls.__new__(cls)
    SCRAPERS[instance.source_name] = cls
    return cls
