"""Structured Data and Schema.org validator (JSON-LD & Microdata)."""
from __future__ import annotations

import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class StructuredDataAuditor:
    """Audits page structured data for Schema.org compliance, JSON-LD validity, and rich snippet types."""

    @staticmethod
    def audit_structured_data(soup: BeautifulSoup) -> tuple[list[str], list[str]]:
        """Extracts and validates JSON-LD schemas and microdata types from page DOM."""
        detected_types: list[str] = []
        issues: list[str] = []

        # 1. Inspect JSON-LD scripts
        scripts = soup.find_all("script", type=lambda t: t and "ld+json" in t.lower())
        for idx, script in enumerate(scripts, 1):
            raw = script.string or script.get_text()
            if not raw or not raw.strip():
                issues.append(f"JSON-LD script block #{idx} is empty")
                continue

            try:
                data = json.loads(raw.strip())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        ctx = item.get("@context", "")
                        schema_type = item.get("@type", "")
                        if "schema.org" not in str(ctx).lower():
                            issues.append(f"JSON-LD block #{idx} missing standard schema.org @context")
                        if schema_type:
                            if isinstance(schema_type, list):
                                detected_types.extend(schema_type)
                            else:
                                detected_types.append(str(schema_type))
                        else:
                            issues.append(f"JSON-LD block #{idx} missing @type declaration")
            except json.JSONDecodeError as err:
                issues.append(f"Invalid JSON syntax in JSON-LD script block #{idx}: {err}")

        # 2. Inspect Microdata
        microdata_items = soup.find_all(attrs={"itemtype": True})
        for item in microdata_items:
            itype = item.get("itemtype", "").strip()
            if itype:
                type_name = itype.split("/")[-1]
                detected_types.append(f"Microdata:{type_name}")

        # Summary check
        if not detected_types:
            issues.append("No structured data (JSON-LD or Microdata) detected; recommended for search rich snippets")

        return detected_types, issues
