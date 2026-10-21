from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from .checks import PAGE_CHECKS, SITE_CHECKS, SPECS, Issue, Severity
from .crawler import SiteData
from .logging_setup import log

logger = logging.getLogger("seo_tool.audit")


@dataclass
class Recommendation:
    check_id: str
    title: str
    category: str
    severity: str
    impact: int
    confidence: float
    affected_pages: int
    priority: float
    recommendation: str
    why: str
    sample_urls: list[str]
    examples: list[str]


@dataclass
class AuditResult:
    issues: list[Issue]
    recommendations: list[Recommendation]
    summary: dict[str, Any]
    check_errors: list[dict[str, str]] = field(default_factory=list)


def run_audit(site: SiteData) -> AuditResult:
    issues: list[Issue] = []
    errors: list[dict[str, str]] = []
    for page in site.pages.values():
        for check in PAGE_CHECKS:
            try:
                issues.extend(check(page, site))
            except Exception as exc:  # one faulty check must not abort the audit
                errors.append({"check": check.__name__, "url": page.url, "error": repr(exc)})
                log(logger, logging.ERROR, "check failed", check=check.__name__, url=page.url, error=repr(exc))
    for check in SITE_CHECKS:
        try:
            issues.extend(check(site))
        except Exception as exc:
            errors.append({"check": check.__name__, "url": site.start_url, "error": repr(exc)})
            log(logger, logging.ERROR, "site check failed", check=check.__name__, error=repr(exc))
    return AuditResult(issues, prioritize(issues), summarize(site, issues), errors)


def prioritize(issues: list[Issue]) -> list[Recommendation]:
    """priority = severity x impact x confidence x (1 + log2(affected pages))."""
    grouped: dict[str, list[Issue]] = defaultdict(list)
    for i in issues:
        grouped[i.check_id].append(i)
    recs = []
    for check_id, items in grouped.items():
        spec = SPECS[check_id]
        urls = list(dict.fromkeys(i.url for i in items))
        score = spec.severity * spec.impact * spec.confidence * (1 + math.log2(len(urls)))
        recs.append(Recommendation(
            check_id, spec.title, spec.category, spec.severity.name, spec.impact, spec.confidence,
            len(urls), round(score, 2), spec.recommendation, spec.why, urls[:20], [i.message for i in items[:5]],
        ))
    recs.sort(key=lambda r: (-r.priority, r.check_id))
    return recs


def summarize(site: SiteData, issues: list[Issue]) -> dict[str, Any]:
    pages = list(site.pages.values())
    sev = Counter(SPECS[i.check_id].severity.name for i in issues)
    robots_ok = bool(site.robots and site.robots.status and 200 <= site.robots.status < 300)
    return {
        "start_url": site.start_url,
        "pages_crawled": len(pages),
        "indexable_pages": sum(p.indexable for p in pages),
        "status_codes": dict(Counter(str(p.status) if p.status else "error" for p in pages)),
        "blocked_by_robots": len(site.blocked),
        "bot_challenges": sum(p.bot_challenge for p in pages),
        "skipped_by_crawl_rules": site.skipped_by_rules,
        "sitemap_urls": len(site.sitemap.urls),
        "links_checked": len(site.link_status),
        "links_unchecked": site.unchecked_links,
        "requests_made": site.requests,
        "duration_seconds": round(site.finished_at - site.started_at, 1),
        "crawl_complete": not (site.limit_reached or site.interrupted),
        "js_rendering": site.config.render_js,
        "ai_crawler_access": site.robots.ai_bots if robots_ok and site.robots else "all allowed (no robots.txt rules)",
        "llms_txt": site.llms_txt,
        "pagespeed_urls": len(site.extras.get("pagespeed", {})),
        "gsc_urls_inspected": len(site.extras.get("gsc", {})),
        "issues_by_severity": {s.name: sev.get(s.name, 0) for s in sorted(Severity, reverse=True)},
        "total_issues": len(issues),
    }
