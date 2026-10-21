from __future__ import annotations

import re
from collections import defaultdict

from ..urls import duplicate_key
from .base import CheckSpec as C, Severity as S, issue, page_check, register, site_check

_SOFT404_RE = re.compile(r"\b(404|not found|page (?:not|doesn.?t|does not) exist|no longer available|"
                         r"nothing (?:was )?found)\b", re.I)

register(
    C("fetch_error", "Page could not be fetched", "indexing", S.HIGH, 4, 0.7,
      "Investigate server/network errors, redirect loops or TLS problems for these URLs.",
      "Pages that cannot be fetched cannot be indexed."),
    C("bot_challenge", "Crawler received a bot challenge", "indexing", S.HIGH, 4, 0.7,
      "Check your CDN/WAF bot settings and make sure verified search-engine and AI-search crawlers are allowed. "
      "This tool does not bypass challenges, so results for these URLs are incomplete.",
      "If real crawlers get the same challenge, these pages can't be indexed or cited."),
    C("status_4xx", "Page returns 4xx", "indexing", S.HIGH, 4, 0.95,
      "Fix or remove links to these URLs; 301-redirect only if a genuinely equivalent page exists.",
      "Linked pages returning errors waste crawl budget and frustrate users."),
    C("status_5xx", "Page returns 5xx", "indexing", S.CRITICAL, 5, 0.9,
      "Fix server errors; persistent 5xx responses cause crawl slowdowns and de-indexing.",
      "Server errors signal an unreliable site to crawlers and users."),
    C("soft_404", "Possible soft 404", "indexing", S.MEDIUM, 3, 0.6,
      "Return a real 404/410 for missing content, or add useful content if the page should exist.",
      "Pages that say 'not found' but return 200 waste crawl budget and are treated as soft 404s. "
      "Detection is English-only and heuristic."),
    C("noindex", "Page is noindex", "indexing", S.INFO, 3, 0.9,
      "Confirm each noindex is intentional; remove it from pages that should rank.",
      "Accidental noindex is a common cause of lost traffic."),
    C("canonical_missing", "No canonical tag", "indexing", S.LOW, 2, 0.7,
      "Add a self-referencing rel=canonical with the preferred absolute URL.",
      "Helps consolidate signals across URL variants (parameters, trailing slashes)."),
    C("canonical_multiple", "Multiple canonical URLs", "indexing", S.HIGH, 4, 0.9,
      "Declare exactly one canonical (HTML or HTTP header, not conflicting).",
      "Conflicting canonicals may cause Google to ignore all of them."),
    C("canonical_cross", "Canonical points elsewhere", "indexing", S.INFO, 2, 0.6,
      "Confirm this page is a duplicate/variant of the canonical target; otherwise self-canonicalise.",
      "A wrong cross-canonical can remove a unique page from search."),
    C("canonical_non_indexable", "Canonical target not indexable", "indexing", S.HIGH, 4, 0.85,
      "Point canonicals directly at a 200, indexable, self-canonical URL.",
      "Canonicals to redirects/errors/noindex pages send mixed signals and are often ignored."),
    C("non200_in_sitemap", "Sitemap lists non-200 URL", "indexing", S.MEDIUM, 3, 0.9,
      "List only final, 200-status URLs in the sitemap.",
      "Sitemaps should contain the canonical URLs you want indexed."),
    C("noindex_in_sitemap", "Sitemap lists noindex URL", "indexing", S.MEDIUM, 3, 0.9,
      "Remove noindex URLs from the sitemap, or remove the noindex if the page should rank.",
      "Contradictory signals between sitemap and robots directives."),
    C("canonicalized_in_sitemap", "Sitemap lists non-canonical URL", "indexing", S.LOW, 2, 0.8,
      "List the canonical URL instead.", "Sitemaps should only contain canonical URLs."),
    C("blocked_in_sitemap", "Sitemap lists robots-blocked URL", "indexing", S.MEDIUM, 3, 0.9,
      "Unblock the URL or remove it from the sitemap.", "Crawlers cannot fetch URLs disallowed in robots.txt."),
    C("not_in_sitemap", "Indexable page not in sitemap", "indexing", S.LOW, 1, 0.5,
      "Add important indexable pages to the XML sitemap.", "Sitemaps help discovery, especially for deep pages."),
    C("orphan_page", "Orphan page (no internal links)", "indexing", S.MEDIUM, 3, 0.6,
      "Link to this page from relevant pages using descriptive anchors, or remove it if obsolete.",
      "Pages without internal links are hard for users and crawlers to find."),
    C("deep_page", "Page is many clicks from home", "indexing", S.LOW, 2, 0.6,
      "Improve navigation/internal links so important pages are within ~3 clicks.",
      "Deeply buried pages tend to be crawled less often."),
    C("duplicate_content", "Duplicate or near-duplicate content", "content", S.MEDIUM, 3, 0.7,
      "Consolidate duplicates (301 or canonical) or make each page genuinely distinct. "
      "Do not just reword pages to dodge detection.",
      "Duplicate pages split signals and offer users no extra value."),
    C("duplicate_url_variants", "Duplicate URL variants", "indexing", S.MEDIUM, 3, 0.8,
      "Pick one URL format (case, trailing slash, parameter order) and 301 or canonicalise the rest.",
      "Multiple URLs for the same page dilute signals and waste crawl budget."),
    C("js_dependent_content", "Content depends on JavaScript", "indexing", S.MEDIUM, 3, 0.5,
      "Server-render or pre-render primary content and links, or confirm Google renders them with URL "
      "Inspection. Many AI crawlers don't run JavaScript. Serve users and crawlers the same content (no cloaking).",
      "JS rendering is deferred and can fail; content missing from HTML may be indexed late or not at all."),
    C("blocked_by_robots", "Internal URL blocked by robots.txt", "indexing", S.INFO, 2, 0.7,
      "Confirm these disallows are intentional. Use noindex (not robots.txt) to keep a page out of search.",
      "Blocked URLs cannot be crawled, but may still be indexed without content if linked."),
)


@page_check
def check_status(page, site):
    if page.bot_challenge:
        yield issue("bot_challenge", page.url, f"HTTP {page.status}: bot challenge or CAPTCHA page received",
                    status=page.status)
        return
    if page.error:
        yield issue("fetch_error", page.url, page.error, status=page.status)
    elif page.status and 400 <= page.status < 500:
        yield issue("status_4xx", page.url, f"HTTP {page.status}", inlinks=page.inlinks)
    elif page.status and page.status >= 500:
        yield issue("status_5xx", page.url, f"HTTP {page.status}")


@page_check
def check_soft_404(page, site):
    if page.ok and page.word_count < 200 and _SOFT404_RE.search(" ".join(filter(None, [page.title, *page.h1s]))):
        yield issue("soft_404", page.url, "Page says 'not found' but returns HTTP 200", title=page.title)


@page_check
def check_robots_and_canonical(page, site):
    if not page.ok:
        return
    if page.is_noindex:
        source = "X-Robots-Tag header" if page.x_robots_tag else "meta robots tag"
        yield issue("noindex", page.url, f"Excluded from indexing via {source}",
                    directives=sorted(page.robots_directives))
    if len(set(page.canonicals)) > 1:
        yield issue("canonical_multiple", page.url, "Conflicting canonical URLs", canonicals=page.canonicals)
    canonical = page.canonical
    if canonical is None:
        if not page.is_noindex:
            yield issue("canonical_missing", page.url, "No canonical URL declared")
        return
    if canonical == page.final_url:
        return
    yield issue("canonical_cross", page.url, f"Canonical points to {canonical}", canonical=canonical)
    if canonical in site.blocked:
        yield issue("canonical_non_indexable", page.url, "Canonical target is blocked by robots.txt",
                    canonical=canonical)
        return
    target, redirects = site.lookup(canonical)
    if target is None:
        return
    problem = None
    if redirects:
        problem = f"canonical target redirects to {target.final_url}"
    elif not target.ok:
        problem = f"canonical target returns HTTP {target.status}"
    elif target.is_noindex:
        problem = "canonical target is noindex"
    elif not target.is_canonical_self:
        problem = f"canonical chain: target canonicalises to {target.canonical}"
    if problem:
        yield issue("canonical_non_indexable", page.url, problem, canonical=canonical)


@page_check
def check_js_dependency(page, site):
    if not page.ok:
        return
    if page.rendered and page.raw_word_count is not None:
        if page.word_count >= 100 and page.raw_word_count < page.word_count * 0.5:
            yield issue("js_dependent_content", page.url,
                        f"{page.raw_word_count} words in raw HTML vs {page.word_count} after rendering")
    elif not page.rendered and (page.empty_js_root or (page.word_count < 50 and page.script_count >= 5)):
        yield issue("js_dependent_content", page.url,
                    "Little content in raw HTML; page may rely on JavaScript. Re-run with --render-js to compare.",
                    word_count=page.word_count, scripts=page.script_count)


@page_check
def check_depth(page, site):
    if page.indexable and page.click_depth is not None and page.click_depth > 3:
        yield issue("deep_page", page.url, f"{page.click_depth} clicks from the start URL")


@site_check
def check_sitemap_consistency(site):
    sm = site.sitemap.urls
    for url in sorted(site.blocked & sm):
        yield issue("blocked_in_sitemap", url, "Listed in sitemap but disallowed by robots.txt")
    if not sm:
        return
    for key, page in site.pages.items():
        if page.in_sitemap:
            if page.redirect_chain and key in sm:
                yield issue("non200_in_sitemap", key, f"Sitemap URL redirects to {page.final_url}")
            elif page.bot_challenge:
                continue
            elif not page.ok:
                yield issue("non200_in_sitemap", key, f"Sitemap URL returns {page.status or page.error}")
            elif page.is_noindex:
                yield issue("noindex_in_sitemap", key, "Sitemap URL is noindex")
            elif not page.is_canonical_self:
                yield issue("canonicalized_in_sitemap", key, f"Canonical is {page.canonical}")
            elif page.inlinks == 0 and key != site.start_url:
                note = " (crawl was partial; links may exist on uncrawled pages)" if site.limit_reached else ""
                yield issue("orphan_page", key, "In sitemap but no internal links found" + note)
        elif page.indexable:
            yield issue("not_in_sitemap", key, "Indexable page missing from sitemap")


@site_check
def check_duplicates(site):
    pages = [p for p in site.pages.values() if p.indexable and p.word_count >= 50 and p.simhash is not None]
    by_hash = defaultdict(list)
    for p in pages:
        by_hash[p.content_hash].append(p)
    for group in by_hash.values():
        if len(group) > 1:
            urls = [p.url for p in group]
            for p in group:
                yield issue("duplicate_content", p.url, f"Identical main content on {len(group)} pages",
                            match="exact", other_urls=[u for u in urls if u != p.url][:10])
    if len(pages) <= 2000:
        for i, a in enumerate(pages):
            for b in pages[i + 1:]:
                if a.content_hash == b.content_hash:
                    continue
                distance = bin(a.simhash ^ b.simhash).count("1")
                if distance <= 3:
                    yield issue("duplicate_content", a.url, f"Near-duplicate of {b.url}",
                                match="near", hamming_distance=distance, other_urls=[b.url])

    groups = defaultdict(list)
    for p in site.pages.values():
        if p.ok and not p.redirect_chain:
            groups[duplicate_key(p.final_url)].append(p)
    for group in groups.values():
        finals = sorted({p.final_url for p in group})
        if len(finals) > 1 and len({p.canonical or p.final_url for p in group}) > 1:
            for p in group:
                yield issue("duplicate_url_variants", p.url,
                            "URL variants resolve to separate 200 pages without a shared canonical",
                            variants=finals)


@site_check
def check_blocked(site):
    for url in sorted(site.blocked):
        yield issue("blocked_by_robots", url, "Linked internally but disallowed by robots.txt")
