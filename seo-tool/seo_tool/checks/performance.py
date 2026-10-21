from __future__ import annotations

from .base import CheckSpec as C, Severity as S, issue, page_check, register

register(
    C("viewport_missing", "Missing/incorrect viewport", "mobile", S.HIGH, 3, 0.85,
      'Add <meta name="viewport" content="width=device-width, initial-scale=1">.',
      "Google uses mobile-first indexing; pages without a viewport render poorly on phones."),
    C("lang_missing", "Missing html lang", "mobile", S.LOW, 1, 0.7,
      'Declare the language, e.g. <html lang="en">.', "Helps accessibility tools and language detection."),
    C("slow_response", "Slow server response", "performance", S.MEDIUM, 2, 0.6,
      "Investigate server time (caching, CDN, DB queries). Measure Core Web Vitals with --pagespeed.",
      "Slow responses hurt users and can reduce crawl rate. This measures time to headers from one location."),
    C("large_html", "Large HTML document", "performance", S.LOW, 1, 0.6,
      "Reduce inline scripts/styles/data in the HTML.", "Large documents slow parsing and rendering."),
    C("render_blocking_scripts", "Render-blocking scripts", "performance", S.LOW, 1, 0.5,
      "Add defer/async to non-critical scripts in <head>.", "Blocking scripts delay first render (LCP)."),
    C("no_compression", "HTML not compressed", "performance", S.LOW, 1, 0.6,
      "Enable gzip or brotli compression for text responses.", "Compression reduces transfer time considerably."),
)


@page_check
def check_mobile_perf(page, site):
    if not page.ok:
        return
    vp = (page.viewport or "").lower()
    if not vp:
        yield issue("viewport_missing", page.url, "No viewport meta tag")
    elif "width=device-width" not in vp:
        yield issue("viewport_missing", page.url, f"Viewport not set to device-width: {page.viewport}")
    if not page.lang:
        yield issue("lang_missing", page.url, "No lang attribute on <html>")
    if page.ttfb > site.config.slow_response_seconds:
        yield issue("slow_response", page.url, f"Time to headers {page.ttfb:.2f}s", ttfb=page.ttfb)
    if page.html_bytes > 1_000_000:
        yield issue("large_html", page.url, f"HTML is {page.html_bytes / 1e6:.1f} MB")
    if page.blocking_scripts >= 3:
        yield issue("render_blocking_scripts", page.url, f"{page.blocking_scripts} blocking scripts in <head>")
    if page.html_bytes > 10_000 and not page.headers.get("content-encoding"):
        yield issue("no_compression", page.url, "No Content-Encoding on HTML response")
