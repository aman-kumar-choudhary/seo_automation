"""GEO (generative engine optimisation) checks: things that can stop AI search features from finding,
reading or accurately quoting a page. Google states AI Overviews / AI Mode have no extra technical
requirements beyond normal SEO; these checks focus on access, snippet controls and clarity."""
from __future__ import annotations

from ..bots import AI_BOTS
from ..parser import ARTICLE_TYPES, VISIBLE_TEXT_CAP, iter_entities, normalize_text
from .base import CheckSpec as C, Severity as S, issue, page_check, register, site_check

ENTITY_TYPES = {"Organization", "Corporation", "LocalBusiness", "Person", "WebSite", "NewsMediaOrganization",
                "OnlineStore", "EducationalOrganization", "GovernmentOrganization", "MedicalOrganization"}
NAMED_TYPES = {"Product", "Recipe", "Event", "Course", "SoftwareApplication", "Book", "Movie"}

register(
    C("ai_search_crawler_blocked", "Search / AI-search crawler blocked by robots.txt", "geo", S.MEDIUM, 3, 0.85,
      "If you want to appear in this product, allow its crawler in robots.txt and in your CDN/WAF. "
      "If blocking is intentional, ignore this.",
      "AI search products generally only show and cite pages their search crawler may fetch; each crawler is "
      "controlled separately."),
    C("ai_training_crawler_blocked", "AI training crawler blocked", "geo", S.INFO, 1, 0.9,
      "No action needed if intentional. Blocking training crawlers does not remove the site from Google Search.",
      "Reported so you can confirm the policy matches your intent."),
    C("snippet_restricted", "Snippet restricted (limits AI features)", "geo", S.MEDIUM, 3, 0.9,
      "Remove nosnippet or raise max-snippet unless restricting previews is intentional.",
      "Google uses nosnippet, data-nosnippet and max-snippet to limit what is shown from a page in Search, "
      "including AI Overviews and AI Mode."),
    C("data_nosnippet_used", "Sections excluded with data-nosnippet", "geo", S.INFO, 1, 0.8,
      "Make sure the excluded sections are not the content you want quoted.",
      "data-nosnippet sections can't be used in snippets or Google's AI features."),
    C("schema_text_mismatch", "Structured data not matching visible text", "geo", S.LOW, 2, 0.5,
      "Make headline/name/question values in structured data match text visible on the page.",
      "Google requires structured data to match visible content; mismatched markup may be ignored or treated "
      "as spammy."),
    C("author_missing", "Article without author information", "geo", S.INFO, 1, 0.4,
      "Show a real author (byline and author in Article markup) where it helps readers judge trust. "
      "Never invent authors or credentials.",
      "Clear authorship helps people and systems assess who stands behind the content."),
    C("date_missing", "Article without publish/update date", "geo", S.INFO, 1, 0.4,
      "Show accurate published/updated dates (and datePublished/dateModified). Only update dates when the "
      "content really changes.",
      "Dates help people and AI systems judge freshness; faking freshness is misleading."),
    C("entity_schema_missing", "No Organization/WebSite markup on home page", "geo", S.LOW, 1, 0.5,
      "Add Organization (or LocalBusiness/Person) and WebSite markup on the home page with name, logo, url "
      "and sameAs links to official profiles.",
      "Helps search engines and AI systems identify the entity behind the site."),
    C("hard_to_scan", "Long page with few subheadings", "geo", S.INFO, 1, 0.4,
      "Split long content into sections with descriptive H2/H3 headings and answer the main question early.",
      "Well-structured text is easier for people to scan and for systems to quote accurately."),
)


@site_check
def check_ai_crawlers(site):
    r = site.robots
    if not r or not r.status or not 200 <= r.status < 300:
        return
    for bot in AI_BOTS:
        if bot.token == "Googlebot" or r.ai_bots.get(bot.token, True):
            continue  # Googlebot is covered by googlebot_blocked
        cid = "ai_search_crawler_blocked" if bot.category == "search" else "ai_training_crawler_blocked"
        yield issue(cid, r.url, f"{bot.token} ({bot.operator}, {bot.purpose}) is disallowed for the start URL",
                    crawler=bot.token, docs=bot.docs)


@page_check
def check_snippet_controls(page, site):
    if not page.indexable:
        return
    ms = page.max_snippet
    if page.is_nosnippet or (ms is not None and 0 <= ms < 50):
        yield issue("snippet_restricted", page.url,
                    "nosnippet set" if page.is_nosnippet else f"max-snippet:{ms}",
                    directives=sorted(page.robots_directives))
    if page.data_nosnippet:
        yield issue("data_nosnippet_used", page.url, f"{page.data_nosnippet} element(s) with data-nosnippet")


def _schema_claims(page) -> list[str]:
    claims: list[str] = []
    for ent in iter_entities(page.json_ld):
        types = ent.get("@type")
        types = set(types) if isinstance(types, list) else {types}
        if types & ARTICLE_TYPES and isinstance(ent.get("headline"), str):
            claims.append(ent["headline"])
        if types & NAMED_TYPES and isinstance(ent.get("name"), str):
            claims.append(ent["name"])
        if "FAQPage" in types:
            for q in ent.get("mainEntity") or []:
                if isinstance(q, dict) and isinstance(q.get("name"), str):
                    claims.append(q["name"])
    return claims


@page_check
def check_schema_consistency(page, site):
    if not page.indexable or not page.json_ld or len(page.visible_text) >= VISIBLE_TEXT_CAP:
        return  # skip when visible text was truncated to avoid false positives
    missing = [c for c in _schema_claims(page)
               if len(normalize_text(c)) >= 10 and normalize_text(c) not in page.visible_text]
    if missing:
        yield issue("schema_text_mismatch", page.url, f"{len(missing)} structured-data value(s) not found in "
                    "visible text", values=missing[:10])


@page_check
def check_article_signals(page, site):
    if not page.indexable or not page.is_article:
        return
    if not page.authors:
        yield issue("author_missing", page.url, "Article has no author in markup or meta tags")
    if not (page.date_published or page.date_modified):
        yield issue("date_missing", page.url, "Article has no datePublished/dateModified or article:*_time")


@page_check
def check_scannability(page, site):
    if page.indexable and page.word_count >= 800:
        subheads = sum(1 for level, _ in page.headings if level in (2, 3))
        if subheads < 2:
            yield issue("hard_to_scan", page.url, f"{page.word_count} words with {subheads} H2/H3 heading(s)")


@site_check
def check_entity_markup(site):
    home = site.pages.get(site.start_url)
    if not home or not home.indexable:
        return
    types = set(home.schema_types)
    if not (types & ENTITY_TYPES or any(t.endswith(("Business", "Organization", "Store")) for t in types)):
        yield issue("entity_schema_missing", home.url, "Home page has no Organization/WebSite-type markup",
                    found=sorted(types))
