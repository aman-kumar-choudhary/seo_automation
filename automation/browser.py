from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Locator

from .screenshots import ScreenshotManager
from .network_resilience import UserAgentRotator, DomainRateLimiter

if TYPE_CHECKING:
    from config import Settings
    from automation.controller import Monitor


class VisibleBrowser:
    """Manages the visible Chromium browser session with DOM highlighting and diagnostics."""

    def __init__(self, settings: Settings, monitor: Monitor | None = None):
        self.settings = settings
        self.monitor = monitor
        self.pw = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.screenshot_mgr = ScreenshotManager(settings.screenshot_dir)
        self.ua_rotator = UserAgentRotator()
        self.rate_limiter = DomainRateLimiter(settings.submission_cooldown_seconds)

    def _verify_display_environment(self) -> None:
        """Verifies that an active graphical desktop display is present when running headed."""
        if not self.settings.headless:
            display = os.environ.get("DISPLAY")
            wayland = os.environ.get("WAYLAND_DISPLAY")
            if not display and not wayland:
                raise RuntimeError(
                    "No graphical desktop display detected ($DISPLAY and $WAYLAND_DISPLAY are unset). "
                    "Cannot launch a visible Chromium window without a graphical environment. "
                    "To execute in a headless server environment, explicitly use: python main.py run --headless"
                )

    async def start(self) -> None:
        """Launches Chromium in headed mode by default with Playwright tracing."""
        self._verify_display_environment()
        self.pw = await async_playwright().start()

        # Headed mode is default unless explicitly configured otherwise
        self.browser = await self.pw.chromium.launch(
            headless=self.settings.headless,
            slow_mo=self.settings.slow_mo,
            args=["--start-maximized"] if not self.settings.headless else [],
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 850},
            user_agent=self.ua_rotator.get_random(),
        )

        # Start Playwright tracing for diagnostics
        self.settings.trace_dir.mkdir(parents=True, exist_ok=True)
        await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)

        self.page = await self.context.new_page()

        mode_msg = (
            "Headless mode explicitly selected."
            if self.settings.headless
            else f"Visible Chromium mode enabled (DISPLAY={os.environ.get('DISPLAY', ':0')}, slow_mo={self.settings.slow_mo}ms)."
        )
        if self.monitor:
            await self.monitor.log(f"Browser launched successfully. {mode_msg}")

    async def goto(self, url: str, timeout: int = 30000) -> None:
        """Navigates to URL and notifies monitoring hub with domain throttling."""
        if not self.page:
            raise RuntimeError("Browser not started.")

        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        if domain:
            waited = await self.rate_limiter.throttle(domain)
            if waited > 0 and self.monitor:
                await self.monitor.log(f"Rate Limiter: Cooldown {waited:.2f}s applied for domain '{domain}'.")

        if self.monitor:
            await self.monitor.log(f"Navigating to {url}.")
            await self.monitor.state(
                operation={
                    "current_website_url": url,
                    "browser_action": "Navigating to URL",
                }
            )

        await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)

        if self.monitor:
            await self.monitor.state(
                operation={
                    "current_website_url": self.page.url,
                    "browser_action": "Page loaded successfully",
                }
            )

    async def open_dashboard(self, url: str) -> Page:
        """Opens the monitoring dashboard in a separate tab without replacing active page."""
        if not self.context:
            raise RuntimeError("Browser context not started.")
        dash_page = await self.context.new_page()
        await dash_page.goto(url, wait_until="domcontentloaded", timeout=15000)
        if self.monitor:
            await self.monitor.log(f"Live monitoring dashboard tab opened at: {url}")
        # Bring the primary automation page back to focus
        if self.page:
            await self.page.bring_to_front()
        return dash_page

    async def highlight(self, locator: Locator, color: str = "#ff9900") -> None:
        """Applies a temporary high-visibility highlight to an element before interaction."""
        try:
            await locator.evaluate(
                f"""(el) => {{
                    el.dataset.seoOriginalStyle = el.getAttribute('style') || '';
                    el.style.outline = '3px solid {color}';
                    el.style.outlineOffset = '2px';
                    el.style.boxShadow = '0 0 12px rgba(255, 153, 0, 0.85)';
                    el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                }}"""
            )
            # Brief visual pause so the user can follow along visually
            await asyncio.sleep(min(0.2, self.settings.slow_mo / 1000.0))
        except Exception:
            pass

    async def unhighlight(self, locator: Locator) -> None:
        """Restores the original element styling after interaction."""
        try:
            await locator.evaluate(
                """(el) => {
                    if (el.dataset.seoOriginalStyle !== undefined) {
                        el.setAttribute('style', el.dataset.seoOriginalStyle);
                        delete el.dataset.seoOriginalStyle;
                    } else {
                        el.style.outline = '';
                        el.style.outlineOffset = '';
                        el.style.boxShadow = '';
                    }
                }"""
            )
        except Exception:
            pass

    async def highlight_and_fill(
        self,
        locator: Locator,
        text: str,
        field_name: str = "",
        human_like: bool = False,
    ) -> None:
        """Highlights an input field, logs action, fills text, and restores original styling."""
        if self.monitor and field_name:
            await self.monitor.log(f"Filling {field_name} field...")
            await self.monitor.state(
                operation={"browser_action": f"Filling {field_name}"}
            )

        await self.highlight(locator)
        if human_like and len(text) <= 120:
            from .human_emulator import HumanEmulator
            await HumanEmulator.human_type(locator, text)
        else:
            await locator.fill(text)
        await self.unhighlight(locator)

        if self.monitor and field_name:
            await self.monitor.log(f"{field_name.capitalize()} field filled successfully.")

    async def highlight_and_click(
        self,
        locator: Locator,
        button_name: str = "button",
        human_like: bool = False,
    ) -> None:
        """Highlights a button or clickable element, logs action, clicks, and unhighlights."""
        if self.monitor:
            await self.monitor.log(f"Clicking {button_name}...")
            await self.monitor.state(
                operation={"browser_action": f"Clicking {button_name}"}
            )

        await self.highlight(locator)
        if human_like and self.page:
            from .human_emulator import HumanEmulator
            await HumanEmulator.human_click(self.page, locator)
        else:
            await locator.click()
        await self.unhighlight(locator)

    async def screenshot(self, label: str = "manual") -> str:
        """Captures a screenshot of the current page and reports it to monitor."""
        if not self.page:
            return ""
        path = await self.screenshot_mgr.capture_manual(self.page, label)
        if self.monitor:
            await self.monitor.log(f"Screenshot captured: {path}")
            await self.monitor.state(last_screenshot=path)
        return path

    async def detect_manual_intervention(self) -> str | None:
        """Checks for CAPTCHA, 2FA, or login blocks requiring human intervention."""
        if not self.page:
            return None

        # Check for CAPTCHA iframes or elements
        captcha_selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            "iframe[src*='turnstile']",
            "div.g-recaptcha",
            "div.h-captcha",
            "#cf-turnstile",
        ]
        for sel in captcha_selectors:
            count = await self.page.locator(sel).count()
            if count > 0:
                return "CAPTCHA verification detected on page"

        # Check for login / 2FA text in main body
        try:
            body_text = (await self.page.inner_text("body", timeout=1500)).lower()
            if "two-factor authentication" in body_text or "enter verification code" in body_text:
                return "Two-factor authentication required"
            if "verify your email" in body_text:
                return "Email verification required"
            if "suspended" in body_text and "account" in body_text:
                return "Account restriction detected"
        except Exception:
            pass

        return None

    async def close(self) -> None:
        """Gracefully closes tracing, pages, context, and browser."""
        if self.context:
            try:
                trace_file = self.settings.trace_dir / "session.zip"
                await self.context.tracing.stop(path=str(trace_file))
                if self.monitor:
                    await self.monitor.log(f"Execution trace saved: {trace_file}")
            except Exception:
                pass

        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass

        if self.pw:
            try:
                await self.pw.stop()
            except Exception:
                pass
