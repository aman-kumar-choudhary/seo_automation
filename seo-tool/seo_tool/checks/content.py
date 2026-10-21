"""Content-quality signals. These are heuristics that start a human review, not rules to optimise towards."""
from __future__ import annotations

from .base import CheckSpec as C, Severity as S, issue, page_check, register, site_check

THIN_WORDS = 150
MAX_DENSITY = 3.0

register(
    C("thin_content", "Little main content", "content", S.LOW, 2, 0.5,
      "Check whether the page fully answers its visitors' needs. Expand only with genuinely useful information, "
      "or consolidate/noindex low-value pages. Word count itself is not a ranking factor.",
      "Pages with little unique value can drag down perceived site quality."),
    C("keyword_overuse", "Possible keyword over-use", "content", S.MEDIUM, 3, 0.5,
      "Rewrite for natural language: use synonyms and write for readers. Never repeat terms to 'hit' a density.",
      "Keyword stuffing violates Google's spam policies and hurts readability."),
    C("keyword_not_covered", "Target keyword not covered", "content", S.INFO, 2, 0.4,
      "Expand or create content only if it genuinely serves people searching this topic. "
      "Don't create thin or doorway pages per keyword variant.",
      "Informational: no crawled indexable page mentions this keyword."),
    C("keyword_cannibalization", "Many pages target the same keyword", "content", S.LOW, 2, 0.4,
      "Make sure each page has a distinct purpose; consolidate pages that compete for the same intent.",
      "Several near-identical pages for one query split signals and can look like doorway pages."),
)


@page_check
def check_content(page, site):
    if not page.indexable:
        return
    if page.word_count < THIN_WORDS:
        yield issue("thin_content", page.url, f"{page.word_count} words of main content", word_count=page.word_count)
    for kw, st in page.keyword_stats.items():
        reasons = []
        if st["density"] > MAX_DENSITY and st["content_count"] >= 5:
            reasons.append(f"density {st['density']}%")
        if st["in_title"] > 1:
            reasons.append(f"{st['in_title']}x in title")
        if st["in_description"] > 2:
            reasons.append(f"{st['in_description']}x in meta description")
        if reasons:
            yield issue("keyword_overuse", page.url, f"'{kw}' may be over-used: {'; '.join(reasons)}",
                        keyword=kw, **st)


@site_check
def check_keyword_coverage(site):
    for kw in site.config.target_keywords:
        pages = [p for p in site.pages.values() if p.indexable and kw in p.keyword_stats]
        if not any(p.keyword_stats[kw]["content_count"] for p in pages):
            yield issue("keyword_not_covered", site.start_url, f"No crawled indexable page mentions '{kw}'",
                        keyword=kw)
            continue
        in_title = [p.url for p in pages if p.keyword_stats[kw]["in_title"]]
        if len(in_title) > 3:
            yield issue("keyword_cannibalization", site.start_url, f"'{kw}' appears in {len(in_title)} titles",
                        keyword=kw, urls=in_title[:20])
