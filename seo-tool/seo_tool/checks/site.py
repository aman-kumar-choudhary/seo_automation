from __future__ import annotations

from .base import CheckSpec as C, Severity as S, issue, page_check, register, site_check

register(
    C("robots_unreachable", "robots.txt unreachable", "site", S.HIGH, 4, 0.8,
      "Make robots.txt return 200 (or 404 if you have no rules). Fix 5xx/timeouts.",
      "When robots.txt is unreachable, crawlers may treat the whole site as disallowed."),
    C("robots_missing", "No robots.txt", "site", S.LOW, 1, 0.8,
      "Optional, but a robots.txt is a good place to declare your sitemap.",
      "Missing robots.txt means 'allow all', which is fine; it just can't advertise sitemaps."),
    C("googlebot_blocked", "Googlebot blocked from start URL", "site", S.CRITICAL, 5, 0.9,
      "Review robots.txt Disallow rules for Googlebot / *.",
      "Blocked pages cannot be crawled by Google, so they can't appear in Search or its AI features."),
    C("sitemap_missing", "No XML sitemap found", "site", S.MEDIUM, 2, 0.8,
      "Publish an XML sitemap of canonical, indexable URLs and reference it in robots.txt / Search Console.",
      "Sitemaps aid discovery, especially for large or poorly linked sites."),
    C("sitemap_not_in_robots", "Sitemap not referenced in robots.txt", "site", S.LOW, 1, 0.7,
      "Add 'Sitemap: <absolute URL>' to robots.txt.", "Helps all crawlers find the sitemap."),
    C("sitemap_error", "Sitemap error", "site", S.MEDIUM, 2, 0.8,
      "Fix unreachable or invalid sitemap files.", "Invalid sitemaps are ignored."),
    C("https_not_used", "Site not served over HTTPS", "security", S.HIGH, 3, 0.95,
      "Serve all pages over HTTPS and 301-redirect HTTP.",
      "HTTPS is a lightweight ranking signal and protects users."),
    C("http_not_redirected", "HTTP does not redirect to HTTPS", "security", S.MEDIUM, 3, 0.85,
      "301-redirect all http:// URLs to their https:// equivalents.", "Prevents duplicate HTTP/HTTPS versions."),
    C("hsts_missing", "No HSTS header", "security", S.INFO, 1, 0.5,
      "Consider Strict-Transport-Security once HTTPS is stable everywhere.",
      "Security hardening; not a ranking factor."),
    C("mixed_content", "Mixed content", "security", S.MEDIUM, 2, 0.9,
      "Load all resources over HTTPS.", "Browsers block or warn on insecure resources on HTTPS pages."),
    C("crawl_incomplete", "Crawl incomplete", "meta", S.INFO, 1, 1.0,
      "Raise max_pages/max_depth (politely) or use --resume for full coverage; site-wide findings are a sample.",
      "Some checks (orphans, duplicates, sitemap coverage) depend on full coverage."),
)


@site_check
def check_robots(site):
    r = site.robots
    if r is None:
        return
    if r.status is None or r.status >= 500 or r.status == 429:
        yield issue("robots_unreachable", r.url, f"robots.txt unreachable ({r.error or r.status})")
    elif r.status >= 400:
        yield issue("robots_missing", r.url, f"robots.txt returned {r.status}")
    elif not r.googlebot_allowed_start:
        yield issue("googlebot_blocked", site.start_url, "robots.txt disallows Googlebot from the start URL")


@site_check
def check_sitemap(site):
    sm = site.sitemap
    if not sm.locations:
        yield issue("sitemap_missing", site.start_url, "No sitemap in robots.txt or at /sitemap.xml")
    elif not sm.from_robots:
        yield issue("sitemap_not_in_robots", site.start_url, f"Found {sm.locations[0]} but not in robots.txt")
    for err in sm.errors:
        yield issue("sitemap_error", err.split(": ", 1)[0], err)


@site_check
def check_https(site):
    if site.start_url.startswith("http://"):
        yield issue("https_not_used", site.start_url, "Start URL uses http://")
    hc = site.http_check
    if hc and hc.status == 200 and not hc.final_url.startswith("https://"):
        yield issue("http_not_redirected", hc.url, "HTTP version serves content without redirecting to HTTPS")
    start = site.pages.get(site.start_url)
    if start and start.final_url.startswith("https://") and start.ok \
            and "strict-transport-security" not in start.headers:
        yield issue("hsts_missing", start.final_url, "No Strict-Transport-Security header")
    if site.limit_reached or site.interrupted:
        reason = "interrupted" if site.interrupted else "limit reached"
        yield issue("crawl_incomplete", site.start_url, f"Crawl stopped after {len(site.pages)} pages ({reason})")


@page_check
def check_mixed_content(page, site):
    if page.ok and page.final_url.startswith("https://"):
        insecure = sorted({r for r in page.resources if r.startswith("http://")})
        if insecure:
            yield issue("mixed_content", page.url, f"{len(insecure)} insecure resource(s)", resources=insecure[:20])
