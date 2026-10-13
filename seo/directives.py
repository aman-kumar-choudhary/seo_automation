"""Canonical tags, robots meta directives, and robots.txt crawler permission auditor."""
from __future__ import annotations

import logging
import urllib.robotparser
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DirectivesAuditor:
    """Audits canonical links, robots meta directives, and server robots.txt."""

    @staticmethod
    def audit_canonical(soup: BeautifulSoup, page_url: str) -> tuple[str, list[str]]:
        """Audits canonical URL configuration ensuring self-referencing and consistent protocols."""
        canonical_tag = soup.find("link", rel=lambda x: x and "canonical" in x)
        canonical_url = canonical_tag.get("href", "").strip() if canonical_tag else ""
        issues: list[str] = []

        if not canonical_url:
            issues.append("Missing canonical <link rel='canonical'> tag")
        else:
            can_parsed = urlparse(canonical_url)
            page_parsed = urlparse(page_url)
            if can_parsed.netloc.lower().removeprefix("www.") != page_parsed.netloc.lower().removeprefix("www."):
                issues.append(f"Cross-domain canonical detected: '{canonical_url}' does not match '{page_url}'")
            elif can_parsed.path.rstrip("/") != page_parsed.path.rstrip("/"):
                issues.append(f"Canonical URL path points to different path: '{can_parsed.path}' vs '{page_parsed.path}'")

        return canonical_url, issues

    @staticmethod
    def audit_robots_meta(soup: BeautifulSoup) -> tuple[str, list[str]]:
        """Audits robots meta tag directives for indexing and link equity blockers."""
        robots_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "robots"})
        content = robots_tag.get("content", "").strip().lower() if robots_tag else "index, follow"
        issues: list[str] = []

        if "noindex" in content:
            issues.append(f"Meta robots directive blocks search indexing: '{content}'")
        if "nofollow" in content:
            issues.append(f"Meta robots directive blocks link equity transmission: '{content}'")

        return content, issues

    @staticmethod
    async def audit_robots_txt(domain: str, test_path: str = "/") -> tuple[str, list[str]]:
        """Fetches and parses robots.txt to verify search crawler permissions."""
        clean_domain = domain.strip().lower().removeprefix("www.")
        robots_url = f"https://{clean_domain}/robots.txt"
        issues: list[str] = []
        status = "VALID"

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 404:
                    status = "MISSING"
                    issues.append("robots.txt not found (HTTP 404)")
                    return status, issues

                if resp.status_code >= 400:
                    status = f"HTTP_{resp.status_code}"
                    issues.append(f"robots.txt returned HTTP status {resp.status_code}")
                    return status, issues

                # Verify if it returns text/plain rather than HTML redirect/parking page
                ctype = resp.headers.get("content-type", "").lower()
                if "html" in ctype or "<html" in resp.text.lower()[:200]:
                    status = "INVALID_FORMAT"
                    issues.append("robots.txt returned HTML content instead of plaintext directives")
                    return status, issues

                # Parse directives
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(resp.text.splitlines())
                allowed = rp.can_fetch("Googlebot", f"https://{clean_domain}{test_path}")
                if not allowed:
                    issues.append(f"Googlebot is disallowed from crawling '{test_path}' by robots.txt")

                # Check for sitemap declaration
                if "sitemap:" not in resp.text.lower():
                    issues.append("No Sitemap directive declared in robots.txt")

        except Exception as exc:
            status = "FETCH_ERROR"
            issues.append(f"Could not retrieve robots.txt: {exc}")

        return status, issues
