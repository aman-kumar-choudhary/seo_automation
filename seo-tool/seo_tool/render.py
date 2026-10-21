"""Optional JS rendering (pip install 'seo-tool[js]' && playwright install chromium)."""
from __future__ import annotations

import logging

from .config import Config
from .logging_setup import log

logger = logging.getLogger("seo_tool.render")
_BLOCKED_RESOURCES = {"image", "media", "font"}  # reduce load on the target server


class JsRenderer:
    def __init__(self, cfg: Config) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("render_js requires: pip install 'seo-tool[js]' && playwright install chromium") from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._context = self._browser.new_context(user_agent=cfg.user_agent)
        self._context.route("**/*", self._route)
        self._timeout_ms = int(cfg.timeout * 1000)

    @staticmethod
    def _route(route) -> None:  # type: ignore[no-untyped-def]
        if route.request.resource_type in _BLOCKED_RESOURCES:
            route.abort()
        else:
            route.continue_()

    def render(self, url: str) -> str | None:
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=self._timeout_ms)
            return page.content()
        except Exception as exc:  # playwright raises several error types
            log(logger, logging.WARNING, "render failed", url=url, error=str(exc))
            return None
        finally:
            page.close()

    def close(self) -> None:
        self._context.close()
        self._browser.close()
        self._pw.stop()
