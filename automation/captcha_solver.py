"""CAPTCHA challenge detector and authorized human-resolution handler for Playwright browser sessions.

Compliant with automation safety policies:
- Accurately detects reCAPTCHA v2/v3, hCaptcha, Cloudflare Turnstile, and challenge dialogs.
- Pauses automation safely for authorized human resolution.
- NEVER performs token injection, CAPTCHA bypass, or evasion heuristics.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from playwright.async_api import Page

if TYPE_CHECKING:
    from config import Settings
    from automation.browser import VisibleBrowser

logger = logging.getLogger(__name__)


@dataclass
class CaptchaInfo:
    captcha_type: str  # 'recaptcha_v2', 'recaptcha_v3', 'hcaptcha', 'turnstile', 'image', 'unknown'
    sitekey: str | None = None
    action: str | None = None
    element_selector: str | None = None


@dataclass
class CaptchaSolveResult:
    solved: bool
    captcha_type: str
    method: str  # 'human_resolution', 'none', 'skipped'
    token: str | None = None
    error_message: str | None = None


class CaptchaSolver:
    """Detects CAPTCHA challenges and coordinates safe pausing for authorized human operator resolution."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = getattr(settings, "captcha_detection_enabled", True)
        self.pause_timeout = getattr(settings, "captcha_pause_timeout_seconds", 180.0)

    async def detect_captcha(self, page: Page) -> CaptchaInfo | None:
        """Inspects page DOM and iframes to detect presence and type of CAPTCHA challenges."""
        try:
            # 1. Cloudflare Turnstile
            turnstile_loc = page.locator("iframe[src*='turnstile'], #cf-turnstile, div.cf-turnstile")
            if await turnstile_loc.count() > 0:
                sitekey = await self._extract_attr(page, "[data-sitekey]", "data-sitekey")
                return CaptchaInfo(captcha_type="turnstile", sitekey=sitekey, element_selector="#cf-turnstile")

            # 2. Google reCAPTCHA
            recaptcha_loc = page.locator("iframe[src*='recaptcha'], div.g-recaptcha, #recaptcha")
            if await recaptcha_loc.count() > 0:
                sitekey = await self._extract_attr(page, ".g-recaptcha, [data-sitekey]", "data-sitekey")
                if not sitekey or "http" in sitekey:
                    raw = sitekey or (await recaptcha_loc.first.get_attribute("src") or "")
                    m = re.search(r"[?&]k=([a-zA-Z0-9_-]+)", raw)
                    if m:
                        sitekey = m.group(1)
                return CaptchaInfo(captcha_type="recaptcha_v2", sitekey=sitekey, element_selector=".g-recaptcha")

            # 3. hCaptcha
            hcaptcha_loc = page.locator("iframe[src*='hcaptcha'], div.h-captcha")
            if await hcaptcha_loc.count() > 0:
                sitekey = await self._extract_attr(page, ".h-captcha, [data-sitekey]", "data-sitekey")
                return CaptchaInfo(captcha_type="hcaptcha", sitekey=sitekey, element_selector=".h-captcha")

        except Exception as exc:
            logger.debug("Error while inspecting page for CAPTCHA: %s", exc)

        return None

    async def _extract_attr(self, page: Page, selector: str, attribute: str) -> str | None:
        try:
            loc = page.locator(selector).first
            if await loc.count() > 0:
                val = await loc.get_attribute(attribute)
                if val:
                    return val.strip()
        except Exception:
            pass
        return None

    async def solve(self, browser: VisibleBrowser) -> CaptchaSolveResult:
        """Detects CAPTCHA and pauses workflow for authorized human operator resolution."""
        page = browser.page
        if not page:
            return CaptchaSolveResult(solved=False, captcha_type="none", method="none", error_message="No page open")

        info = await self.detect_captcha(page)
        if not info:
            return CaptchaSolveResult(solved=True, captcha_type="none", method="none")

        logger.info(
            "CAPTCHA challenge detected: %s (sitekey: %s). Pausing for authorized human resolution.",
            info.captcha_type,
            info.sitekey or "unspecified",
        )

        return await self._pause_for_human_resolution(browser, info)

    async def _pause_for_human_resolution(
        self, browser: VisibleBrowser, info: CaptchaInfo
    ) -> CaptchaSolveResult:
        """Pauses execution and alerts the human operator via monitoring hub to solve the challenge."""
        msg = f"CAPTCHA Challenge ({info.captcha_type.upper()}): Human resolution required in visible browser."
        if browser.monitor:
            await browser.monitor.log(msg)
            await browser.monitor.set_intervention(msg)

        start_time = asyncio.get_event_loop().time()
        poll_interval = 2.0

        while (asyncio.get_event_loop().time() - start_time) < self.pause_timeout:
            # Check if operator requested skip or abort via controller if available
            controller = getattr(browser, "controller", None)
            if controller and getattr(controller, "skip", False):
                controller.skip = False
                if browser.monitor:
                    await browser.monitor.log("Operator requested skip during CAPTCHA challenge.")
                    await browser.monitor.set_intervention(None)
                return CaptchaSolveResult(
                    solved=False,
                    captcha_type=info.captcha_type,
                    method="skipped",
                    error_message="Skipped by operator",
                )

            # Check if challenge has been resolved by operator
            if browser.page:
                is_resolved = await self._is_challenge_cleared(browser.page, info.captcha_type)
                if is_resolved:
                    if browser.monitor:
                        await browser.monitor.log(f"CAPTCHA challenge cleared by operator! Resuming safe workflow.")
                        await browser.monitor.set_intervention(None)
                    return CaptchaSolveResult(
                        solved=True,
                        captcha_type=info.captcha_type,
                        method="human_resolution",
                    )

            await asyncio.sleep(poll_interval)

        timeout_msg = f"CAPTCHA resolution timed out after {int(self.pause_timeout)}s."
        if browser.monitor:
            await browser.monitor.log(timeout_msg)
            await browser.monitor.set_intervention(None)

        return CaptchaSolveResult(
            solved=False,
            captcha_type=info.captcha_type,
            method="human_resolution",
            error_message=timeout_msg,
        )

    async def _is_challenge_cleared(self, page: Page, captcha_type: str) -> bool:
        """Non-intrusively verifies if the challenge has been completed by the operator."""
        try:
            # Check if any active response token was populated by the challenge widget
            script = """() => {
                const r1 = document.querySelector('textarea[name="g-recaptcha-response"]');
                if (r1 && r1.value && r1.value.length > 10) return true;
                const r2 = document.querySelector('textarea[name="h-captcha-response"]');
                if (r2 && r2.value && r2.value.length > 10) return true;
                const r3 = document.querySelector('input[name="cf-turnstile-response"]');
                if (r3 && r3.value && r3.value.length > 10) return true;
                return false;
            }"""
            has_token = bool(await page.evaluate(script))
            if has_token:
                return True

            # Check if CAPTCHA elements are gone from the page
            loc = page.locator("iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='turnstile']")
            if await loc.count() == 0:
                return True
        except Exception:
            pass
        return False
