import asyncio
import random

from playwright.async_api import Page

DELAY_PROFILES: dict[str, tuple[float, float]] = {
    "linkedin": (2.0, 5.0),
    "naukri": (3.0, 6.0),
    "indeed": (1.0, 3.0),
    "glassdoor": (1.0, 3.0),
    "google_jobs": (1.0, 2.0),
    "career_page": (1.0, 2.0),
}


async def random_delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


async def source_delay(source: str) -> None:
    profile = DELAY_PROFILES.get(source, (1.0, 3.0))
    await random_delay(*profile)


async def human_scroll(page: Page, scrolls: int = 3) -> None:
    for _ in range(scrolls):
        distance = random.randint(200, 600)
        await page.mouse.wheel(0, distance)
        await random_delay(0.5, 1.5)


async def human_type(page: Page, selector: str, text: str) -> None:
    element = page.locator(selector)
    await element.click()
    for char in text:
        await element.press_sequentially(char, delay=random.randint(50, 150))


async def random_mouse_move(page: Page) -> None:
    viewport = page.viewport_size or {"width": 1280, "height": 720}
    x = random.randint(100, viewport["width"] - 100)
    y = random.randint(100, viewport["height"] - 100)
    await page.mouse.move(x, y)
    await random_delay(0.2, 0.5)
