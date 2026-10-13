"""Metadata, heading hierarchy, and image alt text auditor."""
from __future__ import annotations

import logging
from bs4 import BeautifulSoup
from .models import ImageAudit

logger = logging.getLogger(__name__)


class MetadataAuditor:
    """Audits title tags, meta descriptions, H1 hierarchy, and image alt text."""

    @staticmethod
    def audit_title(soup: BeautifulSoup) -> tuple[str, int, list[str]]:
        """Audits page title existence and optimal length (30-60 characters)."""
        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True) if title_tag else ""
        length = len(title_text)
        issues: list[str] = []

        if not title_text:
            issues.append("Missing <title> tag")
        elif length < 30:
            issues.append(f"Title is too short ({length} chars; recommended: 30-60)")
        elif length > 65:
            issues.append(f"Title may be truncated in SERPs ({length} chars; recommended: 30-60)")

        return title_text, length, issues

    @staticmethod
    def audit_meta_description(soup: BeautifulSoup) -> tuple[str, int, list[str]]:
        """Audits meta description presence and optimal length (70-160 characters)."""
        desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
        desc_text = desc_tag.get("content", "").strip() if desc_tag else ""
        length = len(desc_text)
        issues: list[str] = []

        if not desc_text:
            issues.append("Missing meta description tag")
        elif length < 70:
            issues.append(f"Meta description is short ({length} chars; recommended: 70-160)")
        elif length > 160:
            issues.append(f"Meta description exceeds optimal length ({length} chars; recommended: 70-160)")

        return desc_text, length, issues

    @staticmethod
    def audit_headings(soup: BeautifulSoup) -> tuple[list[str], list[str]]:
        """Audits H1 element hierarchy ensuring single, descriptive H1 per page."""
        h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
        issues: list[str] = []

        if not h1_tags:
            issues.append("Missing <h1> element")
        elif len(h1_tags) > 1:
            issues.append(f"Multiple <h1> elements detected ({len(h1_tags)} found); recommended: exactly one primary <h1>")

        return h1_tags, issues

    @staticmethod
    def audit_images(soup: BeautifulSoup) -> tuple[list[ImageAudit], int]:
        """Audits images and identifies missing or empty alt attributes."""
        img_tags = soup.find_all("img")
        audits: list[ImageAudit] = []
        missing_count = 0

        for img in img_tags:
            src = img.get("src", "").strip()
            alt = img.get("alt")
            has_alt = alt is not None and len(alt.strip()) > 0

            if not has_alt:
                missing_count += 1

            audits.append(
                ImageAudit(
                    src=src,
                    alt=alt if alt is not None else "",
                    has_alt=has_alt,
                )
            )

        return audits, missing_count
