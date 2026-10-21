from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import AuditResult
from .bots import AI_BOTS
from .crawler import SiteData

SCHEMA_VERSION = "1.2"
DISCLAIMER = ("This audit uses heuristics to flag technical, content and AI-search (GEO) issues. It cannot "
              "guarantee rankings, citations in AI answers, or that a search engine will never treat a site as "
              "spam. Follow Google Search Essentials and confirm findings in Google Search Console.")
GEO_NOTE = ("Google says AI Overviews and AI Mode have no extra technical requirements: a page must be indexed and "
            "eligible to show a snippet. Other AI search products use their own crawlers, listed below.")


def page_row(p) -> dict[str, Any]:
    return {
        "url": p.url, "final_url": p.final_url, "status": p.status, "redirect_hops": len(p.redirect_chain),
        "content_type": p.content_type, "indexable": p.indexable, "noindex": p.is_noindex,
        "nosnippet": p.is_nosnippet, "bot_challenge": p.bot_challenge,
        "canonical": p.canonical or "", "title": p.title or "", "title_length": len(p.title or ""),
        "meta_description": p.meta_description or "", "meta_description_length": len(p.meta_description or ""),
        "h1": " | ".join(p.h1s), "h1_count": len(p.h1s), "word_count": p.word_count, "inlinks": p.inlinks,
        "click_depth": p.click_depth, "in_sitemap": p.in_sitemap, "images": len(p.images),
        "images_missing_alt": sum(i.alt is None for i in p.images), "schema_types": ", ".join(p.schema_types),
        "authors": ", ".join(p.authors[:3]), "date_modified": p.date_modified or "",
        "hreflang_count": len(p.hreflang), "lang": p.lang or "",
        "ttfb_s": p.ttfb, "html_bytes": p.html_bytes, "rendered": p.rendered, "error": p.error or "",
    }


def issue_row(i, evidence_as_text: bool = True) -> dict[str, Any]:
    s = i.spec
    ev = json.dumps(i.evidence, ensure_ascii=False, default=str) if evidence_as_text else i.evidence
    return {"severity": s.severity.name, "check_id": i.check_id, "category": s.category, "title": s.title,
            "url": i.url, "message": i.message, "evidence": ev}


def geo_overview(site: SiteData) -> dict[str, Any]:
    r = site.robots
    robots_ok = bool(r and r.status and 200 <= r.status < 300)
    return {
        "note": GEO_NOTE,
        "crawlers": [{**asdict(b), "allowed": (r.ai_bots.get(b.token, True) if robots_ok and r else True)}
                     for b in AI_BOTS],
        "llms_txt": site.llms_txt,
    }


def write_json(path: Path, site: SiteData, audit: AuditResult, proposals: list) -> None:
    data = {
        "schema_version": SCHEMA_VERSION,
        "disclaimer": DISCLAIMER,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": site.config.to_dict(),
        "summary": audit.summary,
        "geo": geo_overview(site),
        "recommendations": [asdict(r) for r in audit.recommendations],
        "issues": [issue_row(i, evidence_as_text=False) for i in audit.issues],
        "pages": [page_row(p) for p in site.pages.values()],
        "robots": asdict(site.robots) if site.robots else None,
        "sitemap": {"locations": site.sitemap.locations, "url_count": len(site.sitemap.urls),
                    "errors": site.sitemap.errors},
        "external_signals": site.extras,
        "proposals": [asdict(p) for p in proposals],
        "check_errors": audit.check_errors,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _md(text: Any) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def write_markdown(path: Path, site: SiteData, audit: AuditResult, proposals: list) -> None:
    lines = [f"# SEO + GEO audit: {site.start_url}", "", f"_{DISCLAIMER}_", "", "## Summary", ""]
    lines += [f"- **{k}**: {v}" for k, v in audit.summary.items() if k != "ai_crawler_access"]

    geo = geo_overview(site)
    lines += ["", "## GEO / AI search readiness", "", f"_{GEO_NOTE}_", "",
              "| Crawler | Operator | Used for | Allowed on start URL |", "|---|---|---|---|"]
    lines += [f"| {c['token']} | {c['operator']} | {_md(c['purpose'])} | {'yes' if c['allowed'] else '**no**'} |"
              for c in geo["crawlers"]]
    llms = {True: "present", False: "not found", None: "not checked"}[site.llms_txt]
    geo_recs = [r for r in audit.recommendations if r.category == "geo"]
    lines += ["", f"- llms.txt: {llms} (unofficial proposal; reported only, no action recommended)",
              f"- GEO recommendation types: {len(geo_recs)} (category 'geo' below)", ""]

    lines += ["## Prioritized recommendations", ""]
    for n, r in enumerate(audit.recommendations, 1):
        lines += [
            f"### {n}. {r.title} — {r.severity} (priority {r.priority})", "",
            f"- Category: {r.category} | affected pages: {r.affected_pages}",
            f"- Impact {r.impact}/5, confidence {int(r.confidence * 100)}%",
            f"- **Why:** {r.why}", f"- **Recommendation:** {r.recommendation}", "- Examples:",
            *[f"  - {e}" for e in r.examples], *[f"  - <{u}>" for u in r.sample_urls[:5]], "",
        ]
    if proposals:
        lines += ["## Proposed metadata changes (pending review, nothing applied)", "",
                  "| URL | Field | Before | After | Why |", "|---|---|---|---|---|"]
        lines += [f"| {_md(p.url)} | {p.field} | {_md(p.before)} | {_md(p.after)} | {_md(p.reason)} |"
                  for p in proposals]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_all(out: Path, site: SiteData, audit: AuditResult, proposals: list) -> None:
    write_json(out / "audit.json", site, audit, proposals)
    write_csv(out / "issues.csv", [issue_row(i) for i in audit.issues])
    write_csv(out / "pages.csv", [page_row(p) for p in site.pages.values()])
    write_csv(out / "recommendations.csv",
              [{**asdict(r), "sample_urls": " ".join(r.sample_urls), "examples": " | ".join(r.examples)}
               for r in audit.recommendations])
    write_markdown(out / "report.md", site, audit, proposals)


def print_console(audit: AuditResult, out: Path, proposals: list, site: SiteData | None = None,
                  top: int = 10) -> None:
    s = audit.summary
    print(f"\nSEO + GEO audit — {s['start_url']}")
    print(f"Pages: {s['pages_crawled']} (indexable {s['indexable_pages']}) | requests {s['requests_made']} | "
          f"{s['duration_seconds']}s")
    if not s["crawl_complete"]:
        print("NOTE: crawl stopped at the configured limit or was interrupted — site-wide results are a sample. "
              "Use --resume to continue.")
    if s["bot_challenges"]:
        print(f"NOTE: {s['bot_challenges']} URL(s) returned a bot challenge; those results are incomplete.")
    print("Status codes:", ", ".join(f"{k}: {v}" for k, v in sorted(s["status_codes"].items())))
    print("Issues:", ", ".join(f"{k} {v}" for k, v in s["issues_by_severity"].items()))
    if site:
        blocked = [c["token"] for c in geo_overview(site)["crawlers"] if not c["allowed"]]
        print("AI/search crawlers blocked on start URL:", ", ".join(blocked) if blocked else "none")
    print(f"\nTop {min(top, len(audit.recommendations))} recommendations:")
    for n, r in enumerate(audit.recommendations[:top], 1):
        print(f"{n:>2}. [{r.severity:<8}] {r.title} ({r.category}) — {r.affected_pages} page(s), "
              f"priority {r.priority}")
        print(f"     -> {r.recommendation}")
    print(f"\n{len(proposals)} metadata proposal(s) pending review. Nothing on the site was changed.")
    print(f"Reports: {out}")
    print(f"\n{DISCLAIMER}")
