from __future__ import annotations

import re

from .base import CheckSpec as C, Severity as S, issue, page_check, register

# ISO 639-1 language, optional script, optional ISO 3166-1 alpha-2 region, or x-default
_HREFLANG_RE = re.compile(r"^(x-default|[a-z]{2}(-[a-z]{4})?(-[a-z]{2})?)$", re.I)

register(
    C("hreflang_invalid", "Invalid hreflang value", "international", S.MEDIUM, 3, 0.85,
      "Use an ISO 639-1 language code, optionally with an ISO 3166-1 alpha-2 region (en, en-GB, x-default). "
      "The United Kingdom is GB, not UK.",
      "Invalid hreflang codes are ignored."),
    C("hreflang_no_self", "hreflang set without self-reference", "international", S.LOW, 2, 0.7,
      "Include the page itself in its hreflang set.",
      "Each language version should list itself and all alternates."),
    C("hreflang_no_return", "hreflang missing return link", "international", S.MEDIUM, 3, 0.8,
      "Make each alternate page link back to this page with hreflang.",
      "Google ignores hreflang annotations that the other page doesn't confirm."),
    C("hreflang_target_not_indexable", "hreflang points to non-indexable URL", "international", S.MEDIUM, 3, 0.8,
      "Point hreflang only at 200, indexable, self-canonical URLs.",
      "Alternates that redirect, error or canonicalise elsewhere break the hreflang cluster."),
)


def valid_hreflang(code: str) -> bool:
    return bool(_HREFLANG_RE.match(code.strip()))


@page_check
def check_hreflang(page, site):
    if not page.indexable or not page.hreflang:
        return
    bad = [c for c, _ in page.hreflang if not valid_hreflang(c) or c.lower().endswith("-uk")]
    if bad:
        yield issue("hreflang_invalid", page.url, f"Invalid hreflang value(s): {', '.join(bad[:10])}", invalid=bad)
    own = {page.url, page.final_url}
    if not own & {u for _, u in page.hreflang}:
        yield issue("hreflang_no_self", page.url, "Page's hreflang set doesn't include itself")
    for code, url in page.hreflang:
        if url in own:
            continue
        if url in site.blocked:
            yield issue("hreflang_target_not_indexable", page.url, f"hreflang {code} -> {url} is blocked by robots.txt",
                        target=url)
            continue
        target, redirects = site.lookup(url)
        if target is None:
            continue  # not crawled
        if redirects or not target.indexable:
            yield issue("hreflang_target_not_indexable", page.url,
                        f"hreflang {code} -> {url} is not an indexable canonical page", target=url, status=target.status)
        elif not own & {u for _, u in target.hreflang}:
            yield issue("hreflang_no_return", page.url, f"{url} ({code}) does not link back with hreflang", target=url)
