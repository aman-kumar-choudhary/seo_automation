from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import Page


class ScreenshotManager:
    """Manages screenshot captures with diagnostic timestamps and metadata."""

    def __init__(self, screenshot_dir: Path | str = "screenshots"):
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _generate_path(self, prefix: str, label: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:19]
        safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in label)
        filename = f"{prefix}_{safe_label}_{timestamp}.png"
        return self.screenshot_dir / filename

    async def capture(self, page: Page, prefix: str, label: str, full_page: bool = True) -> str:
        """Capture screenshot from a Playwright Page and save to disk."""
        target_path = self._generate_path(prefix, label)
        try:
            await page.screenshot(path=str(target_path), full_page=full_page)
            return str(target_path)
        except Exception:
            # Fallback to viewport screenshot if full-page screenshot fails (e.g. on infinite scroll or cross-origin canvas)
            try:
                await page.screenshot(path=str(target_path), full_page=False)
                return str(target_path)
            except Exception as exc:
                return f"SCREENSHOT_FAILED: {exc}"

    async def capture_before_submission(self, page: Page, platform_name: str) -> str:
        return await self.capture(page, "before", platform_name)

    async def capture_after_submission(self, page: Page, platform_name: str, success: bool) -> str:
        prefix = "published" if success else "failed"
        return await self.capture(page, prefix, platform_name)

    async def capture_error(self, page: Page, platform_name: str) -> str:
        return await self.capture(page, "error", platform_name)

    async def capture_manual(self, page: Page, label: str = "manual_inspect") -> str:
        return await self.capture(page, "manual", label)
