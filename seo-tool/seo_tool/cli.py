from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .ai import generate_ai_proposals
from .audit import run_audit
from .changes import StaticSiteAdapter, apply_proposals, generate_proposals, review, rollback, save_proposals
from .checks import Severity
from .config import Config
from .crawler import Crawler
from .integrations.pagespeed import run_pagespeed
from .integrations.search_console import inspect_urls
from .logging_setup import setup_logging
from .report import print_console, write_all
from .state import CrawlState
from .urls import normalize_url


def _sample(site, n: int) -> list[str]:
    pages = sorted((p for p in site.pages.values() if p.indexable and not p.redirect_chain),
                   key=lambda p: -p.inlinks)
    return [p.url for p in pages[:n]]


def cmd_audit(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config, {
        "max_pages": args.max_pages, "max_depth": args.max_depth, "crawl_delay": args.delay,
        "allow_private_networks": True if args.allow_private_networks else None,
        "render_js": args.render_js, "check_external_links": False if args.no_external else None,
        "target_keywords": args.keywords, "output_dir": args.output_dir, "log_level": args.log_level,
        "exclude_patterns": args.exclude, "max_query_params": args.max_query_params,
        "pagespeed_urls": args.pagespeed, "gsc_property": args.gsc_property,
        "gsc_credentials_file": args.gsc_credentials, "ai_suggestions": args.ai, "brand_voice": args.brand_voice,
    })
    host = urlsplit(args.url).hostname or "site"
    out = Path(cfg.output_dir) / f"{host}-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    setup_logging(cfg.log_level, out / "audit.log")

    state = CrawlState(Path(cfg.output_dir) / f"{host}.crawlstate.sqlite")
    start = normalize_url(args.url, strip_tracking=cfg.strip_tracking_params) or args.url
    if not args.resume:
        state.clear(start)
    crawler = Crawler(cfg)
    try:
        site = crawler.crawl(args.url, state=state)
    finally:
        crawler.fetcher.close()
        state.close()

    if cfg.pagespeed_urls:
        site.extras["pagespeed"] = run_pagespeed(_sample(site, cfg.pagespeed_urls), cfg.pagespeed_strategy)
    if cfg.gsc_property:
        try:
            site.extras["gsc"] = inspect_urls(_sample(site, cfg.gsc_urls), cfg.gsc_property,
                                              cfg.gsc_credentials_file)
        except RuntimeError as exc:
            print(f"warning: Search Console skipped: {exc}", file=sys.stderr)

    audit = run_audit(site)
    proposals = generate_proposals(site, audit.issues, cfg.target_keywords)
    if cfg.ai_suggestions:
        proposals = generate_ai_proposals(site, audit.issues, proposals, cfg)
    save_proposals(out / "proposals.json", proposals)
    write_all(out, site, audit, proposals)
    print_console(audit, out, proposals, site)

    if args.fail_on and any(i.spec.severity >= Severity[args.fail_on.upper()] for i in audit.issues):
        return 2
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    setup_logging(cfg.log_level)
    review(Path(args.proposals), cfg.target_keywords)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    setup_logging("INFO")
    path = Path(args.proposals)
    out = Path(args.output_dir) if args.output_dir else path.parent
    dry_run = not args.execute
    if args.auto:
        print("Automated mode: pending proposals with confidence >= 0.8 and no warnings will also be applied.")
    if dry_run:
        print("DRY RUN: showing diffs only. No files will be modified.\n")
    result = apply_proposals(path, StaticSiteAdapter(args.site_root, args.base_url), out,
                             dry_run=dry_run, auto=args.auto)
    if dry_run:
        print("\nDry run complete. Re-run with --execute to apply (a backup is created first).")
    else:
        print(f"\nApplied {result['applied']} change(s); skipped {result['skipped']}.")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    setup_logging("INFO")
    n = rollback(Path(args.backup_dir), force=args.force)
    print(f"Rolled back {n} proposal(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seo-tool", description="Responsible, white-hat SEO + GEO auditing.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="Crawl a site and write reports (read-only).")
    a.add_argument("url")
    a.add_argument("--config")
    a.add_argument("--max-pages", type=int)
    a.add_argument("--max-depth", type=int)
    a.add_argument("--delay", type=float, help="seconds between requests per host (min 0.5)")
    a.add_argument("--allow-private-networks", action="store_true",
                   help="allow localhost/private targets only in an isolated, controlled environment")
    a.add_argument("--render-js", action="store_true", default=None)
    a.add_argument("--no-external", action="store_true", help="skip external link checks")
    a.add_argument("--keywords", help="comma-separated target keywords")
    a.add_argument("--exclude", action="append", help="regex of URLs not to crawl (repeatable)")
    a.add_argument("--max-query-params", type=int, help="skip discovered URLs with more query parameters (0 = off)")
    a.add_argument("--output-dir")
    a.add_argument("--log-level")
    a.add_argument("--fail-on", choices=[s.name.lower() for s in Severity],
                   help="exit 2 if issues at/above this severity")
    a.add_argument("--resume", action="store_true", help="continue an interrupted or limited crawl")
    a.add_argument("--pagespeed", type=int, help="run PageSpeed Insights on the top N pages")
    a.add_argument("--gsc-property", help="Search Console property, e.g. sc-domain:example.com")
    a.add_argument("--gsc-credentials", help="service-account JSON key file")
    a.add_argument("--ai", action="store_true", default=None, help="AI metadata suggestions (review required)")
    a.add_argument("--brand-voice", help="short description of the brand voice for AI suggestions")
    a.set_defaults(func=cmd_audit)

    r = sub.add_parser("review", help="Interactively approve/reject/edit proposals.")
    r.add_argument("proposals")
    r.add_argument("--config")
    r.set_defaults(func=cmd_review)

    ap = sub.add_parser("apply", help="Apply approved proposals to a local static site (dry run by default).")
    ap.add_argument("proposals")
    ap.add_argument("--site-root", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--execute", action="store_true", help="actually write files (default: dry run)")
    ap.add_argument("--auto", action="store_true",
                    help="automated mode: also apply clean high-confidence pending proposals")
    ap.add_argument("--output-dir")
    ap.set_defaults(func=cmd_apply)

    rb = sub.add_parser("rollback", help="Restore files from a backup directory.")
    rb.add_argument("backup_dir")
    rb.add_argument("--force", action="store_true")
    rb.set_defaults(func=cmd_rollback)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
