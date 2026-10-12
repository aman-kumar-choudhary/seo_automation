"""Human-like interaction emulator with typing jitter, mouse curve movement, and natural delays."""
from __future__ import annotations

import asyncio
import random
from playwright.async_api import Page, Locator

KEYBOARD_NEIGHBORS = {
    "a": "s", "b": "v", "c": "x", "d": "s", "e": "r", "f": "d",
    "g": "f", "h": "g", "i": "u", "j": "h", "k": "j", "l": "k",
    "m": "n", "n": "b", "o": "p", "p": "o", "q": "w", "r": "e",
    "s": "a", "t": "r", "u": "y", "v": "c", "w": "q", "x": "z",
    "y": "t", "z": "x"
}


class HumanEmulator:
    """Emulates human physical interaction variance to bypass heuristic bot pattern detection."""

    @staticmethod
    async def natural_pause(min_sec: float = 0.3, max_sec: float = 0.9) -> None:
        """Micro-pause simulating cognitive reading and orientation."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    async def human_type(
        locator: Locator,
        text: str,
        min_delay_ms: int = 20,
        max_delay_ms: int = 65,
        typo_rate: float = 0.02,
    ) -> None:
        """Types text character-by-character with natural timing jitter and realistic typo corrections."""
        await locator.focus()
        for char in text:
            # Simulate occasional natural human typo
            if random.random() < typo_rate and char.lower() in KEYBOARD_NEIGHBORS:
                typo_char = KEYBOARD_NEIGHBORS[char.lower()]
                await locator.press_sequentially(typo_char, delay=random.randint(min_delay_ms, max_delay_ms))
                await asyncio.sleep(random.uniform(0.08, 0.2))
                await locator.press("Backspace")
                await asyncio.sleep(random.uniform(0.05, 0.15))

            delay = random.randint(min_delay_ms, max_delay_ms)
            await locator.press_sequentially(char, delay=delay)
            # Occasional slightly longer pause between words
            if char in (" ", ".", ","):
                await asyncio.sleep(random.uniform(0.08, 0.25))

    @staticmethod
    async def human_click(page: Page, locator: Locator) -> None:
        """Moves mouse naturally toward target element and clicks with human variance."""
        try:
            box = await locator.bounding_box()
            if box:
                # Add random offset within target element boundaries
                offset_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                offset_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                await page.mouse.move(offset_x, offset_y, steps=random.randint(6, 12))
                await asyncio.sleep(random.uniform(0.05, 0.15))
        except Exception:
            pass

        await locator.click()
        await HumanEmulator.natural_pause(0.2, 0.5)

    @staticmethod
    async def human_scroll(page: Page, delta_y: int = 300) -> None:
        """Smoothly scrolls page with incremental wheel steps."""
        steps = random.randint(3, 6)
        step_delta = delta_y / steps
        for _ in range(steps):
            await page.mouse.wheel(0, step_delta)
            await asyncio.sleep(random.uniform(0.05, 0.12))
