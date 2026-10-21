from __future__ import annotations

from .base import CheckSpec as C, Severity as S, issue, page_check, register

register(
    C("cwv_field_poor", "Poor Core Web Vitals (real-user data)", "performance", S.HIGH, 3, 0.9,
      "Fix the failing metric: LCP (server time, render-blocking resources, hero image), INP (long JavaScript "
      "tasks), CLS (reserve space for images, ads and embeds). Confirm in Search Console's Core Web Vitals report.",
      "Chrome UX Report field data reflects real visitors; Core Web Vitals are part of page experience signals."),
    C("lighthouse_performance_low", "Low Lighthouse performance score (lab)", "performance", S.LOW, 2, 0.5,
      "Use the Lighthouse opportunities as a to-do list. Lab scores vary between runs.",
      "Lab data is a diagnostic aid, not what Google uses to judge page experience."),
    C("gsc_not_indexed", "Google reports page not indexed", "indexing", S.HIGH, 4, 0.9,
      "Fix the cause shown in the coverage state (canonical, noindex, soft 404, quality) instead of "
      "resubmitting repeatedly.",
      "This is Google's own index status, more reliable than any crawler heuristic."),
    C("gsc_canonical_mismatch", "Google chose a different canonical", "indexing", S.MEDIUM, 3, 0.85,
      "Make internal links, sitemap, redirects and rel=canonical agree on one URL. "
      "If pages really are duplicates, consolidate them.",
      "Google ignores declared canonicals when other signals disagree."),
)


@page_check
def check_pagespeed(page, site):
    data = site.extras.get("pagespeed", {}).get(page.url)
    if not data or data.get("error"):
        return
    field = data.get("field") or {}
    slow = {k: v for k, v in (field.get("metrics") or {}).items() if v.get("category") == "SLOW"}
    if slow:
        yield issue("cwv_field_poor", page.url,
                    "Slow: " + ", ".join(f"{k} p75={v.get('p75')}" for k, v in slow.items()),
                    scope=field.get("scope"), metrics=slow)
    perf = (data.get("lab") or {}).get("performance")
    if perf is not None and perf < 50:
        yield issue("lighthouse_performance_low", page.url,
                    f"Lighthouse performance {perf}/100 ({data.get('strategy')})")


@page_check
def check_gsc(page, site):
    r = site.extras.get("gsc", {}).get(page.url)
    if not r:
        return
    if r.get("verdict") not in (None, "PASS") and page.indexable:
        yield issue("gsc_not_indexed", page.url, r.get("coverageState") or f"verdict {r.get('verdict')}", **r)
    g, u = r.get("googleCanonical"), r.get("userCanonical")
    if g and u and g != u:
        yield issue("gsc_canonical_mismatch", page.url, f"Google canonical {g} vs declared {u}",
                    google_canonical=g, user_canonical=u)
