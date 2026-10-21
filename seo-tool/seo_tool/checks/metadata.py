from __future__ import annotations

from collections import defaultdict

from .base import CheckSpec as C, Severity as S, issue, page_check, register, site_check

TITLE_MAX, TITLE_MIN, DESC_MIN, DESC_MAX = 60, 10, 50, 160

register(
    C("title_missing", "Missing title tag", "metadata", S.HIGH, 4, 0.95,
      "Add a unique, descriptive <title> that accurately summarises the page.",
      "Titles are a primary source for search-result title links and help users choose a result."),
    C("title_multiple", "Multiple title tags", "metadata", S.MEDIUM, 2, 0.9,
      "Keep exactly one <title> in <head>.", "Multiple titles make it ambiguous which one is used."),
    C("title_too_long", "Title may be truncated", "metadata", S.LOW, 2, 0.6,
      f"Consider a more concise title (roughly <= {TITLE_MAX} characters), most important words first.",
      "Long titles are often truncated or rewritten; Google measures pixel width, so this is approximate."),
    C("title_too_short", "Very short title", "metadata", S.LOW, 2, 0.6,
      "Make the title descriptive enough to distinguish this page from others.",
      "Very short titles rarely describe a page well and are more likely to be rewritten."),
    C("title_duplicate", "Duplicate title across pages", "metadata", S.MEDIUM, 3, 0.85,
      "Give each indexable page a title reflecting its specific content. If pages are true duplicates, "
      "consolidate (301 or canonical) instead of rewording.",
      "Duplicate titles make pages hard to tell apart and often signal duplicate content."),
    C("meta_description_missing", "Missing meta description", "metadata", S.MEDIUM, 2, 0.9,
      "Write a concise, accurate human-written summary of the page.",
      "Not a ranking factor, but it may be used as the snippet; otherwise one is generated from page text."),
    C("meta_description_length", "Meta description length", "metadata", S.LOW, 1, 0.5,
      f"Aim for a summary of roughly {DESC_MIN}-{DESC_MAX} characters.",
      "Very short descriptions are unhelpful; long ones get truncated."),
    C("meta_description_duplicate", "Duplicate meta description", "metadata", S.LOW, 2, 0.8,
      "Write page-specific descriptions or remove boilerplate ones.",
      "Identical descriptions give users no reason to pick one page over another."),
)


@page_check
def check_title(page, site):
    if not page.indexable:
        return
    if not page.title:
        yield issue("title_missing", page.url, "No <title> or empty title")
        return
    if page.title_count > 1:
        yield issue("title_multiple", page.url, f"{page.title_count} <title> elements found")
    n = len(page.title)
    if n > TITLE_MAX:
        yield issue("title_too_long", page.url, f"Title is {n} characters", title=page.title)
    elif n < TITLE_MIN:
        yield issue("title_too_short", page.url, f"Title is {n} characters", title=page.title)


@page_check
def check_description(page, site):
    if not page.indexable:
        return
    d = page.meta_description
    if not d:
        yield issue("meta_description_missing", page.url, "No meta description")
    elif not DESC_MIN <= len(d) <= DESC_MAX:
        yield issue("meta_description_length", page.url, f"Description is {len(d)} characters", description=d)


def _duplicates(site, attr: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for p in site.pages.values():
        value = getattr(p, attr)
        if p.indexable and value:
            groups[value.strip().lower()].append(p.url)
    return {k: v for k, v in groups.items() if len(v) > 1}


@site_check
def check_duplicate_metadata(site):
    for check_id, attr in (("title_duplicate", "title"), ("meta_description_duplicate", "meta_description")):
        for value, urls in _duplicates(site, attr).items():
            for u in urls:
                yield issue(check_id, u, f"Shared by {len(urls)} pages", value=value,
                            other_urls=[x for x in urls if x != u][:10])
