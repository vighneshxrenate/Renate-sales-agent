import asyncio
import random


async def random_delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


async def human_type(page, selector: str, text: str, min_delay_ms: int = 50, max_delay_ms: int = 150) -> None:
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char, delay=random.randint(min_delay_ms, max_delay_ms))
    await random_delay(0.3, 0.8)


async def human_scroll(page, scrolls: int = 3, direction: str = "down") -> None:
    for _ in range(scrolls):
        delta = random.randint(200, 600)
        if direction == "up":
            delta = -delta
        await page.mouse.wheel(0, delta)
        await random_delay(0.5, 1.5)


async def human_mouse_move(page, x: int, y: int) -> None:
    steps = random.randint(5, 15)
    await page.mouse.move(x, y, steps=steps)
    await random_delay(0.1, 0.3)


async def random_distraction(page) -> None:
    actions = [
        lambda: human_scroll(page, scrolls=random.randint(1, 2)),
        lambda: human_mouse_move(page, random.randint(100, 800), random.randint(100, 600)),
        lambda: random_delay(1.0, 3.0),
    ]
    action = random.choice(actions)
    await action()
