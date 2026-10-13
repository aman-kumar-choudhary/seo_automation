"""XML Sitemap existence, format, and validity auditor."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
import httpx

logger = logging.getLogger(__name__)


class SitemapAuditor:
    """Audits XML sitemap presence, XML syntax validity, and listed URL structures."""

    @staticmethod
    async def audit_sitemap(domain: str) -> tuple[str, str, int, list[str]]:
        """Audits XML sitemap on domain, returning status, sitemap_url, total_urls, and issues."""
        clean_domain = domain.strip().lower().removeprefix("www.")
        candidate_urls = [
            f"https://{clean_domain}/sitemap.xml",
            f"https://{clean_domain}/sitemap_index.xml",
        ]

        issues: list[str] = []
        status = "NOT_FOUND"
        sitemap_url = ""
        total_urls = 0

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for url in candidate_urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        sitemap_url = url
                        content = resp.text.strip()

                        # Detect if server returned an HTML error/parking page instead of XML
                        if "<html" in content.lower()[:200]:
                            status = "INVALID_FORMAT"
                            issues.append(f"Sitemap at '{url}' returned HTML instead of valid XML")
                            return status, sitemap_url, 0, issues

                        # Parse XML syntax
                        try:
                            root = ET.fromstring(content)
                            tag = root.tag.lower()
                            if "urlset" in tag:
                                status = "VALID"
                                # Count <url> elements
                                urls = root.findall(".//{*}url") or root.findall("url")
                                total_urls = len(urls)
                                if total_urls == 0:
                                    issues.append(f"Sitemap at '{url}' contains 0 <url> entries")
                                return status, sitemap_url, total_urls, issues
                            elif "sitemapindex" in tag:
                                status = "VALID_INDEX"
                                sitemaps = root.findall(".//{*}sitemap") or root.findall("sitemap")
                                total_urls = len(sitemaps)
                                return status, sitemap_url, total_urls, issues
                            else:
                                status = "UNRECOGNIZED_ROOT"
                                issues.append(f"Sitemap root element '{root.tag}' is neither urlset nor sitemapindex")
                                return status, sitemap_url, 0, issues
                        except ET.ParseError as xml_err:
                            status = "MALFORMED_XML"
                            issues.append(f"XML parsing error in sitemap: {xml_err}")
                            return status, sitemap_url, 0, issues

                except Exception as exc:
                    logger.debug("Sitemap fetch error for %s: %s", url, exc)

        issues.append(f"No XML sitemap found at standard locations for {clean_domain}")
        return status, "", 0, issues
