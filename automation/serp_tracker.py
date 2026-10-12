"""Organic SERP Ranking and Search Visibility Tracker for Innovions target keywords."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class SERPRankingResult:
    keyword: str
    target_domain: str
    search_engine: str
    rank_position: int | None = None
    found_url: str | None = None
    page_title: str | None = None
    snippet: str | None = None
    total_results_checked: int = 0
    checked_at: str = ""

    @property
    def is_ranked(self) -> bool:
        return self.rank_position is not None

    def to_dict(self) -> dict:
        return asdict(self)


class SERPTracker:
    """Monitors organic search engine rankings for target SEO keywords."""

    def __init__(self, target_domain: str = "innovions.org", timeout_seconds: float = 10.0):
        self.target_domain = target_domain.lower().removeprefix("www.")
        self.timeout = timeout_seconds

    async def check_keyword(
        self,
        keyword: str,
        search_engine: str = "duckduckgo",
        max_results: int = 30,
    ) -> SERPRankingResult:
        """Searches organic SERP listings for the target keyword and finds domain rank position."""
        ts = datetime.now(timezone.utc).isoformat()
        encoded = quote_plus(keyword)

        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return SERPRankingResult(
                        keyword=keyword,
                        target_domain=self.target_domain,
                        search_engine=search_engine,
                        checked_at=ts,
                    )

                soup = BeautifulSoup(resp.text, "html.parser")
                result_nodes = soup.select(".result, .web-result")
                rank = 0

                for node in result_nodes:
                    link_el = node.select_one(".result__url, .result__a, a[href*='//']")
                    if not link_el:
                        continue
                    rank += 1

                    raw_href = link_el.get("href", "")
                    # Extract clean target link from DuckDuckGo redirect wrapper
                    actual_href = raw_href
                    if "uddg=" in raw_href:
                        m = re.search(r"uddg=([^&]+)", raw_href)
                        if m:
                            actual_href = unquote(m.group(1))

                    parsed = urlparse(actual_href)
                    domain = parsed.netloc.lower().removeprefix("www.")

                    title_el = node.select_one(".result__title, .result__a")
                    title = title_el.get_text(strip=True) if title_el else ""

                    snippet_el = node.select_one(".result__snippet")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    if self.target_domain in domain:
                        return SERPRankingResult(
                            keyword=keyword,
                            target_domain=self.target_domain,
                            search_engine=search_engine,
                            rank_position=rank,
                            found_url=actual_href,
                            page_title=title,
                            snippet=snippet,
                            total_results_checked=len(result_nodes),
                            checked_at=ts,
                        )

                    if rank >= max_results:
                        break

                return SERPRankingResult(
                    keyword=keyword,
                    target_domain=self.target_domain,
                    search_engine=search_engine,
                    rank_position=None,
                    total_results_checked=rank,
                    checked_at=ts,
                )
        except Exception as exc:
            logger.warning("SERP check failed for keyword '%s': %s", keyword, exc)
            return SERPRankingResult(
                keyword=keyword,
                target_domain=self.target_domain,
                search_engine=search_engine,
                total_results_checked=0,
                checked_at=ts,
            )
