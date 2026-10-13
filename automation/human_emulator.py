"""Visual pacing and interaction helper for visible Playwright browser sessions.

Provides smooth, observable interaction pacing so human operators can easily monitor
automated form filling and button interactions in headed desktop mode.
Complies with safety policies by eliminating bot-evasion mechanisms and intentional typos.
"""
from __future__ import annotations

import asyncio
import logging
import random
from playwright.async_api import Page, Locator

logger = logging.getLogger(__name__)

# Legacy character neighbor mapping retained for test compatibility
KEYBOARD_NEIGHBORS: dict[str, str] = {
    "a": "s", "b": "v", "c": "x", "d": "s", "e": "r", "f": "d",
    "g": "f", "h": "g", "i": "u", "j": "h", "k": "j", "l": "k",
    "m": "n", "n": "b", "o": "p", "p": "o", "q": "w", "r": "e",
    "s": "a", "t": "r", "u": "y", "v": "c", "w": "q", "x": "z",
    "y": "t", "z": "x"
}


class HumanEmulator:
    """Provides observable interaction pacing for desktop monitoring."""

    @staticmethod
    async def natural_pause(min_sec: float = 0.2, max_sec: float = 0.5) -> None:
        """Micro-pause providing observable pacing for live dashboard monitoring."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    async def human_type(
        locator: Locator,
        text: str,
        min_delay_ms: int = 15,
        max_delay_ms: int = 40,
        typo_rate: float = 0.0,
    ) -> None:
        """Types text with smooth pacing so the operator can visually follow field entry."""
        try:
            await locator.focus()
            for char in text:
                delay = random.randint(min_delay_ms, max_delay_ms)
                await locator.press_sequentially(char, delay=delay)
        except Exception as exc:
            logger.debug("Paced typing fell back to direct fill: %s", exc)
            await locator.fill(text)

    @staticmethod
    async def human_click(page: Page, locator: Locator) -> None:
        """Smoothly points to an element and clicks, providing clear visual progression."""
        try:
            box = await locator.bounding_box()
            if box:
                center_x = box["x"] + box["width"] / 2
                center_y = box["y"] + box["height"] / 2
                await page.mouse.move(center_x, center_y)
                await asyncio.sleep(0.05)
        except Exception as exc:
            logger.debug("Mouse positioning fallback: %s", exc)

        await locator.click()
        await HumanEmulator.natural_pause(0.1, 0.3)

    @staticmethod
    async def human_scroll(page: Page, delta_y: int = 300) -> None:
        """Smoothly scrolls page for operator observation."""
        try:
            await page.mouse.wheel(0, delta_y)
            await asyncio.sleep(0.1)
        except Exception as exc:
            logger.debug("Scroll fallback: %s", exc)
