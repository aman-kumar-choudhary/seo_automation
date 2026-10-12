from __future__ import annotations

import re
import hashlib
from database.models import Draft
from .templates import PLATFORM_TEMPLATES, get_template_style
from .keywords import KeywordClusterManager, RotationStrategy


_CLUSTER_MGR = KeywordClusterManager(RotationStrategy.RELEVANCE_WEIGHTED)


def make_draft(
    platform_name: str,
    keyword: str,
    target_url: str,
    domain: str = "",
    seed: int | None = None,
    cluster_manager: KeywordClusterManager | None = None,
) -> Draft:
    """Generates unique, platform-tailored SEO content draft containing the keyword, cluster terms, and target URL."""
    style_key = get_template_style(platform_name, domain)
    template_bundle = PLATFORM_TEMPLATES.get(style_key, PLATFORM_TEMPLATES["general"])

    mgr = cluster_manager or _CLUSTER_MGR
    kw_bundle = mgr.get_variations_for_platform(platform_name, style_key)

    # Determine stable variation index based on platform domain/name
    if seed is None:
        hasher = hashlib.md5(f"{platform_name}:{domain}".encode())
        val = int(hasher.hexdigest(), 16)
    else:
        val = seed

    titles = template_bundle["title_templates"]
    descriptions = template_bundle["description_templates"]

    title_tmpl = titles[val % len(titles)]
    desc_tmpl = descriptions[val % len(descriptions)]

    title = title_tmpl.format(keyword=keyword, target_url=target_url)
    description = desc_tmpl.format(keyword=keyword, target_url=target_url)

    # Enforce semantic enrichment if not already present
    if kw_bundle["secondary_phrase"].lower() not in description.lower():
        description += f" Key focus areas include {kw_bundle['secondary_phrase']} and high-reliability data capture."

    tags = f"{template_bundle['tags']}, {kw_bundle['secondary_phrase'].replace(' ', '-')}"

    return Draft(
        title=title,
        description=description,
        target_url=target_url,
        tags=tags,
    )


def validate(draft: Draft, keyword: str, target_url: str) -> tuple[bool, str | None]:
    """Validates that draft adheres to SEO requirements without keyword stuffing."""
    # 1. Primary keyword must be present
    full_text = f"{draft.title} {draft.description}"
    keyword_matches = re.findall(rf"\b{re.escape(keyword)}\b", full_text, re.IGNORECASE)
    if not keyword_matches:
        return False, f"Primary keyword '{keyword}' is missing"

    # 2. Exact target URL must match
    if draft.target_url != target_url:
        return False, f"Target URL mismatch: expected {target_url}, got {draft.target_url}"

    if target_url not in draft.description:
        return False, "Exact target URL missing from description"

    # 3. Length checks
    if len(draft.title.strip()) < 15:
        return False, "Title is too short (minimum 15 characters)"
    if len(draft.title.strip()) > 120:
        return False, "Title is too long (maximum 120 characters)"
    if len(draft.description.strip()) < 40:
        return False, "Description is too short (minimum 40 characters)"

    # 4. Prevent keyword stuffing (count must not exceed reasonable frequency)
    word_count = len(full_text.split())
    if len(keyword_matches) > 5 or (word_count >= 15 and (len(keyword_matches) / word_count) > 0.15):
        return False, f"Keyword stuffing detected: keyword '{keyword}' appears {len(keyword_matches)} times"

    return True, None
