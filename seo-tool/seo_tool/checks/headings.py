from __future__ import annotations

from .base import CheckSpec as C, Severity as S, issue, page_check, register

register(
    C("h1_missing", "Missing H1", "content", S.MEDIUM, 2, 0.8,
      "Add one visible main heading that describes the page topic.",
      "A clear main heading helps users and search engines understand the page."),
    C("h1_multiple", "Multiple H1 headings", "content", S.INFO, 1, 0.4,
      "Usually fine (Google says so); just make sure the hierarchy is logical.",
      "Flagged for review only; multiple H1s are not a problem by themselves."),
    C("heading_skip", "Skipped heading levels", "content", S.INFO, 1, 0.5,
      "Use headings in order (H2 under H1, H3 under H2) to reflect structure.",
      "Logical heading structure improves accessibility and scannability."),
    C("heading_empty", "Empty heading", "content", S.LOW, 1, 0.8,
      "Remove empty heading tags or give them meaningful text.",
      "Empty headings confuse screen readers and add no structure."),
)


@page_check
def check_headings(page, site):
    if not page.indexable:
        return
    h1s = page.h1s
    if not h1s:
        yield issue("h1_missing", page.url, "No H1 heading")
    elif len(h1s) > 1:
        yield issue("h1_multiple", page.url, f"{len(h1s)} H1 headings", h1s=h1s[:5])
    if any(not text for _, text in page.headings):
        yield issue("heading_empty", page.url, "Page contains empty heading tags")
    prev, skips = 0, []
    for level, text in page.headings:
        if prev and level > prev + 1:
            skips.append(f"H{prev} -> H{level} ({text[:40]})")
        prev = level
    if skips:
        yield issue("heading_skip", page.url, f"{len(skips)} skipped heading level(s)", examples=skips[:5])
