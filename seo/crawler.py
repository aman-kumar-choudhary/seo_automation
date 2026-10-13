"""Technical site crawler with redirect tracking, TTFB latency measurement, and broken link detection."""
from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urljoin, urlparse
from typing import Any
import httpx
from bs4 import BeautifulSoup
from .models import RedirectHop

logger = logging.getLogger(__name__)


class SiteCrawler:
    """Asynchronous technical crawler for discovering pages, analyzing status codes, and detecting broken links."""

    def __init__(
        self,
        base_url: str = "https://innovions.org/",
        max_pages: int = 15,
        timeout_seconds: float = 10.0,
        concurrency: int = 4,
    ):
        self.base_url = base_url.strip()
        parsed = urlparse(self.base_url)
        self.target_domain = parsed.netloc.lower().removeprefix("www.")
        self.target_scheme = parsed.scheme or "https"
        self.max_pages = max_pages
        self.timeout = timeout_seconds
        self.semaphore = asyncio.Semaphore(concurrency)

    async def crawl_page(self, client: httpx.AsyncClient, url: str) -> dict[str, Any]:
        """Fetches a single page, tracking redirect hops and recording TTFB."""
        redirect_chain: list[RedirectHop] = []
        start = time.perf_counter()

        try:
            # Manually track redirects to log each hop code
            current_url = url
            resp = None
            for _ in range(5):
                resp = await client.get(current_url, follow_redirects=False)
                if resp.is_redirect:
                    redirect_chain.append(RedirectHop(url=current_url, status_code=resp.status_code))
                    loc = resp.headers.get("location")
                    if not loc:
                        break
                    current_url = urljoin(current_url, loc)
                else:
                    break

            ttfb_ms = round((time.perf_counter() - start) * 1000, 2)
            status_code = resp.status_code if resp else 500
            html = resp.text if resp and resp.status_code < 400 else ""
            final_url = current_url

            return {
                "url": final_url,
                "requested_url": url,
                "status_code": status_code,
                "ttfb_ms": ttfb_ms,
                "redirect_chain": redirect_chain,
                "html": html,
            }
        except Exception as exc:
            ttfb_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.debug("Crawl error for %s: %s", url, exc)
            return {
                "url": url,
                "requested_url": url,
                "status_code": 500,
                "ttfb_ms": ttfb_ms,
                "redirect_chain": redirect_chain,
                "html": "",
                "error": str(exc),
            }

    async def crawl_site(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Crawls up to max_pages within the target domain and verifies internal link reachability."""
        visited: set[str] = set()
        to_visit: list[str] = [self.base_url]
        crawled_pages: list[dict[str, Any]] = []
        broken_links: list[dict[str, Any]] = []

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; InnovionsTechnicalAuditor/1.0; +https://innovions.org/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            while to_visit and len(crawled_pages) < self.max_pages:
                current_url = to_visit.pop(0)
                norm_url = self._normalize_url(current_url)

                if norm_url in visited or not self._is_internal(norm_url):
                    continue
                visited.add(norm_url)

                async with self.semaphore:
                    page_data = await self.crawl_page(client, norm_url)
                    crawled_pages.append(page_data)

                    # Extract internal links from page HTML
                    if page_data["html"]:
                        soup = BeautifulSoup(page_data["html"], "html.parser")
                        for a in soup.find_all("a", href=True):
                            href = a["href"].strip()
                            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                                continue
                            full_link = urljoin(norm_url, href)
                            clean_link = self._normalize_url(full_link)
                            if self._is_internal(clean_link) and clean_link not in visited:
                                to_visit.append(clean_link)

            # Check reachability of discovered internal links
            all_internal_targets: set[str] = set()
            for p in crawled_pages:
                if p["html"]:
                    soup = BeautifulSoup(p["html"], "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                            continue
                        full_link = self._normalize_url(urljoin(p["url"], href))
                        if self._is_internal(full_link) and full_link not in visited:
                            all_internal_targets.add(full_link)

            # Sample check unvisited internal targets to catch broken links
            for target in list(all_internal_targets)[:10]:
                try:
                    head_resp = await client.head(target, follow_redirects=True)
                    if head_resp.status_code >= 400:
                        broken_links.append({"url": target, "status_code": head_resp.status_code})
                except Exception as exc:
                    broken_links.append({"url": target, "status_code": 500, "error": str(exc)})

        return crawled_pages, broken_links

    def _is_internal(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower().removeprefix("www.")
        return netloc == self.target_domain or not netloc

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        clean_path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
        return f"{parsed.scheme or self.target_scheme}://{parsed.netloc.lower()}{clean_path}"
