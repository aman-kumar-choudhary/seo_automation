"""Technical SEO Backlink Auditor for Social Bookmarking and Referral Links.

Audits published bookmark links, checks dofollow/nofollow/ugc attributes,
robots meta indexability, anchor text keyword relevance, canonicalization, and TTFB.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass
class BacklinkAuditResult:
    published_url: str
    target_url: str
    link_found: bool = False
    is_dofollow: bool = False
    rel_attribute: str = ""
    anchor_text: str = ""
    has_primary_keyword: bool = False
    meta_robots: str = "index, follow"
    canonical_url: str = ""
    status_code: int = 200
    ttfb_ms: float = 0.0
    quality_score: int = 0
    issues: list[str] = None
    audit_timestamp: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("issues") is None:
            d["issues"] = []
        return d


class TechnicalSEOAuditor:
    """Audits live referral links and bookmarks to evaluate actual backlink equity and indexability."""

    def __init__(self, primary_keyword: str = "RFID", timeout_seconds: float = 12.0):
        self.primary_keyword = primary_keyword.strip().lower()
        self.timeout_seconds = timeout_seconds

    async def audit_url(
        self,
        published_url: str,
        target_url: str,
        page: Page | None = None,
    ) -> BacklinkAuditResult:
        """Audits a published URL for backlink quality using HTTP request or active Playwright page."""
        timestamp = datetime.now(timezone.utc).isoformat()
        issues: list[str] = []
        target_parsed = urlparse(target_url)
        target_domain = target_parsed.netloc.lower().removeprefix("www.")

        html_content = ""
        status_code = 200
        ttfb_ms = 0.0

        if page:
            try:
                html_content = await page.content()
                current_url = page.url
                published_url = current_url or published_url
            except Exception as exc:
                logger.warning("Could not read page content from Playwright: %s", exc)

        if not html_content:
            # Fetch via httpx with TTFB latency measurement
            start_time = time.perf_counter()
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 InnovionsAuditor/1.0",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
                async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
                    resp = await client.get(published_url, headers=headers)
                    ttfb_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    status_code = resp.status_code
                    html_content = resp.text
                    x_robots = resp.headers.get("x-robots-tag", "")
                    if x_robots and "noindex" in x_robots.lower():
                        issues.append(f"HTTP Header X-Robots-Tag contains: {x_robots}")
            except Exception as exc:
                ttfb_ms = round((time.perf_counter() - start_time) * 1000, 2)
                issues.append(f"Network request failed: {exc}")
                return BacklinkAuditResult(
                    published_url=published_url,
                    target_url=target_url,
                    link_found=False,
                    status_code=status_code or 500,
                    ttfb_ms=ttfb_ms,
                    quality_score=0,
                    issues=issues,
                    audit_timestamp=timestamp,
                )

        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Inspect Robots Meta Tag
        robots_meta = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
        meta_robots_val = robots_meta.get("content", "").strip() if robots_meta else "index, follow"
        if "noindex" in meta_robots_val.lower():
            issues.append(f"Meta robots contains noindex: '{meta_robots_val}' (page will not be indexed by Google)")

        # 2. Inspect Canonical URL
        canonical_tag = soup.find("link", rel=lambda x: x and "canonical" in x)
        canonical_url = canonical_tag.get("href", "").strip() if canonical_tag else ""

        # 3. Locate Target Link
        links = soup.find_all("a", href=True)
        matching_link = None
        for a in links:
            href = a["href"].strip()
            parsed_href = urlparse(href)
            href_domain = parsed_href.netloc.lower().removeprefix("www.")
            if href == target_url or (href_domain and href_domain == target_domain):
                matching_link = a
                break

        if not matching_link:
            issues.append(f"Target URL '{target_url}' (domain: {target_domain}) not detected in page DOM")
            return BacklinkAuditResult(
                published_url=published_url,
                target_url=target_url,
                link_found=False,
                meta_robots=meta_robots_val,
                canonical_url=canonical_url,
                status_code=status_code,
                ttfb_ms=ttfb_ms,
                quality_score=0,
                issues=issues,
                audit_timestamp=timestamp,
            )

        # 4. Analyze Link Attributes
        rel_vals = matching_link.get("rel", [])
        if isinstance(rel_vals, str):
            rel_vals = rel_vals.split()
        rel_str = " ".join(rel_vals).lower()

        is_nofollow = "nofollow" in rel_str
        is_ugc = "ugc" in rel_str
        is_sponsored = "sponsored" in rel_str
        is_dofollow = not (is_nofollow or is_ugc or is_sponsored)

        # 5. Analyze Anchor Text
        anchor_text = matching_link.get_text(strip=True)
        has_primary_kw = self.primary_keyword in anchor_text.lower() or "innovions" in anchor_text.lower()

        # 6. Compute Quality Score (0 - 100)
        score = 80  # Base passing link score

        if is_dofollow:
            score += 15
        else:
            if is_nofollow:
                score -= 20
                issues.append("Link rel contains 'nofollow' (does not pass direct PageRank)")
            if is_ugc:
                score -= 10
                issues.append("Link rel contains 'ugc' (user generated content tag)")
            if is_sponsored:
                score -= 25
                issues.append("Link rel contains 'sponsored'")

        if has_primary_kw:
            score += 10
        else:
            issues.append(f"Anchor text '{anchor_text}' lacks primary keyword '{self.primary_keyword}'")

        if "noindex" in meta_robots_val.lower():
            score = 0
        elif ttfb_ms > 2500:
            score -= 10
            issues.append(f"Slow response time: {ttfb_ms}ms")

        final_score = max(0, min(100, score))

        return BacklinkAuditResult(
            published_url=published_url,
            target_url=target_url,
            link_found=True,
            is_dofollow=is_dofollow,
            rel_attribute=rel_str,
            anchor_text=anchor_text,
            has_primary_keyword=has_primary_kw,
            meta_robots=meta_robots_val,
            canonical_url=canonical_url,
            status_code=status_code,
            ttfb_ms=ttfb_ms,
            quality_score=final_score,
            issues=issues,
            audit_timestamp=timestamp,
        )
