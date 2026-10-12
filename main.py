#!/usr/bin/env python3
"""Innovions SEO Social Bookmarking Automation CLI and Entrypoint."""
from __future__ import annotations

import argparse
import asyncio
import sys
import uvicorn
from config import Settings
from database.repository import Repository
from database.models import Status
from dashboard.app import EventHub, create_app
from automation.browser import VisibleBrowser
from automation.controller import WorkflowController
from platforms.discovery import discover
from platforms.metrics import MetricsProvider
from platforms.eligibility import decision
from reports.report_generator import export, export_html, export_json, generate_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Innovions SEO Social Bookmarking Automation with Live Browser Monitoring"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Launch the monitoring dashboard and visible Chromium browser")
    run_parser.add_argument("--headless", action="store_true", help="Explicitly enable headless execution (default: headed visible browser)")
    run_parser.add_argument("--dry-run", action="store_true", help="Execute a visible dry run without publishing bookmarks")
    run_parser.add_argument("--limit", type=int, default=None, help="Limit the number of platform submissions")
    run_parser.add_argument("--continuous", action="store_true", help="Run in continuous auto-loop mode (never stops, searches web for new platforms)")
    run_parser.add_argument("--auto", action="store_true", help="Full automated auto-pilot (continuous auto-search + automatic draft approval)")
    run_parser.add_argument("--interval", type=int, default=30, help="Interval in seconds between continuous auto-search cycles (default: 30)")

    # auto command
    auto_parser = subparsers.add_parser("auto", help="Launch fully automated continuous auto-task (never stops, searches & automates)")
    auto_parser.add_argument("--headless", action="store_true", help="Explicitly enable headless execution")
    auto_parser.add_argument("--live", action="store_true", help="Enable live publishing (disables default safe dry run)")
    auto_parser.add_argument("--limit", type=int, default=None, help="Limit number of submissions per cycle")
    auto_parser.add_argument("--interval", type=int, default=30, help="Interval in seconds between auto-search cycles")

    # discover command
    subparsers.add_parser("discover", help="Discover candidate social bookmarking platforms")

    # verify-metrics command
    subparsers.add_parser("verify-metrics", help="Fetch and evaluate SEO authority metrics from authorized provider")

    # generate-content command
    subparsers.add_parser("generate-content", help="Generate and validate SEO content drafts for eligible platforms")

    # report command
    rep_parser = subparsers.add_parser("report", help="Export structured CSV, HTML, and JSON reports and summary statistics")
    rep_parser.add_argument("--format", choices=["csv", "html", "json", "all"], default="all", help="Output report format (default: all)")

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Audit live backlink attributes, indexability, anchor text, and TTFB")
    audit_parser.add_argument("--url", required=True, help="Published bookmark or referral page URL to audit")
    audit_parser.add_argument("--target", default="https://innovions.org/", help="Target website URL (default: https://innovions.org/)")

    # hard-dry-test command
    hdt_parser = subparsers.add_parser("hard-dry-test", help="Execute an automated hard dry test across N social media SEO platforms")
    hdt_parser.add_argument("--count", "-n", type=int, default=5, help="Number of Social Media SEO platforms to automate (default: 5)")
    hdt_parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (default: headed visible Chromium)")
    hdt_parser.add_argument("--slow-mo", type=int, default=300, help="Playwright slow_mo delay in milliseconds (default: 300)")

    # check-serp command
    serp_parser = subparsers.add_parser("check-serp", help="Check organic SERP ranking positions for target keywords")
    serp_parser.add_argument("--keyword", default="RFID", help="Target keyword (default: RFID)")
    serp_parser.add_argument("--domain", default="innovions.org", help="Target domain (default: innovions.org)")

    # check-health command
    health_parser = subparsers.add_parser("check-health", help="Ping and validate availability/latency of candidate platforms")
    health_parser.add_argument("--domain", default=None, help="Optional specific domain to check")

    # test-notification command
    notif_parser = subparsers.add_parser("test-notification", help="Test outbound webhook notifications")
    notif_parser.add_argument("--message", default="Innovions SEO Automation test notification", help="Message text")

    return parser


async def run_metrics_verification(settings: Settings, repo: Repository) -> None:
    provider = MetricsProvider(settings)
    platforms = repo.platforms()
    print(f"Evaluating SEO metrics for {len(platforms)} platform(s)...")
    for row in platforms:
        domain = row["domain"]
        values = await provider.fetch(domain)
        status, reason = decision(values, settings)
        repo.set_metrics(row["id"], values or {}, status, reason)
        metrics_display = f"DA: {values['da']}, PA: {values.get('pa', '-')}, Spam: {values['spam_score']}%" if values else "No authorized metrics"
        reason_display = f" — {reason}" if reason else ""
        print(f"[{status}] {row['name']} ({domain}) | {metrics_display}{reason_display}")


async def run_server_and_browser(settings: Settings) -> None:
    repo = Repository(settings.database_path)
    hub = EventHub()
    browser = VisibleBrowser(settings, None)
    controller = WorkflowController(settings, repo, hub, browser)
    browser.monitor = controller.monitor

    app = create_app(hub, settings.screenshot_dir)
    config = uvicorn.Config(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    print(f"Live Monitoring Dashboard: http://{settings.dashboard_host}:{settings.dashboard_port}")
    print(f"Browser mode: {'HEADLESS (explicitly enabled)' if settings.headless else 'VISIBLE CHROMIUM (headed mode with live desktop window)'}")
    print(f"Dry run mode: {'ACTIVE (submissions will not be published)' if settings.dry_run else 'DISABLED'}")

    try:
        # Wait for FastAPI dashboard server to start
        while not server.started:
            await asyncio.sleep(0.05)

        # Launch visible browser window and navigate to target URL
        await browser.start()
        await browser.goto(settings.target_url)

        # Open dashboard interface in browser
        dashboard_url = f"http://{settings.dashboard_host}:{settings.dashboard_port}"
        await browser.open_dashboard(dashboard_url)

        # Initialize controller state and start workflow task
        await controller.initialize()
        workflow_task = asyncio.create_task(controller.run())

        # Listen for dashboard commands (Pause, Resume, Stop, Approve, Reject, Screenshot)
        await controller.handle_commands()

        await workflow_task
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutdown requested by user.")
    except Exception as exc:
        print(f"\nExecution error: {type(exc).__name__}: {exc}")
    finally:
        print("Closing browser and saving execution trace...")
        await browser.close()
        server.should_exit = True
        await server_task
        print("Shutdown complete. Progress saved in database.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings()

    if args.command in ("run", "auto"):
        if args.command == "auto":
            settings.continuous = True
            settings.manual_approval = False
            settings.dry_run = not getattr(args, "live", False)
            if args.headless:
                settings.headless = True
            if getattr(args, "limit", None) is not None:
                settings.run_limit = args.limit
        else:
            if args.headless:
                settings.headless = True
            if args.dry_run:
                settings.dry_run = True
            if args.limit is not None:
                settings.run_limit = args.limit
            if getattr(args, "continuous", False) or getattr(args, "auto", False):
                settings.continuous = True
            if getattr(args, "auto", False):
                settings.manual_approval = False
            if hasattr(args, "interval") and args.interval:
                settings.loop_interval_seconds = args.interval

        asyncio.run(run_server_and_browser(settings))
        return

    repo = Repository(settings.database_path)

    if args.command == "discover":
        count = asyncio.run(discover(repo, settings))
        print(f"Discovered and recorded {count} unique candidate platforms in {settings.database_path}.")

    elif args.command == "verify-metrics":
        asyncio.run(run_metrics_verification(settings, repo))

    elif args.command == "generate-content":
        from content.generator import make_draft, validate

        eligible_platforms = repo.platforms((Status.ELIGIBLE,))
        if not eligible_platforms:
            print("No ELIGIBLE platforms found. (Platforms require DA >= 20, Spam Score < 10% from authorized provider).")
            return

        print(f"Generating content drafts for {len(eligible_platforms)} eligible platform(s)...")
        for row in eligible_platforms:
            draft = make_draft(row["name"], settings.keyword, settings.target_url, row["domain"])
            valid, reason = validate(draft, settings.keyword, settings.target_url)
            repo.save_draft(row["id"], draft.title, draft.description, draft.target_url, draft.tags, valid)
            print(f"Draft generated for {row['name']} | Valid: {valid} | Title: '{draft.title}'")

    elif args.command == "report":
        fmt = getattr(args, "format", "all")
        summary = generate_summary(repo)
        
        if fmt in ("csv", "all"):
            csv_file = export(repo, settings.output_dir)
            print(f"CSV Report:  {csv_file}")
        if fmt in ("html", "all"):
            html_file = export_html(repo, settings.output_dir, settings.target_url, settings.keyword)
            print(f"HTML Report: {html_file}")
        if fmt in ("json", "all"):
            json_file = export_json(repo, settings.output_dir)
            print(f"JSON Report: {json_file}")

        print(f"\n--- Execution & SEO Summary ---")
        print(f"Total Platforms: {summary['total_platforms']}")
        print(f"Eligibility Breakdown: {summary['eligibility_breakdown']}")
        print(f"Submission Breakdown: {summary['submission_breakdown']}")
        audits = summary.get("backlink_audits", {})
        if audits and audits.get("total_audits"):
            print(f"Backlink Audits: {audits['total_audits']} total | Quality: {audits['avg_quality_score']}/100 | Dofollow: {audits['dofollow_ratio']}%")

    elif args.command == "audit":
        from automation.seo_auditor import TechnicalSEOAuditor

        print(f"Auditing backlink attributes for: {args.url}")
        print(f"Target URL: {args.target}")
        auditor = TechnicalSEOAuditor(primary_keyword=settings.keyword)
        audit_res = asyncio.run(auditor.audit_url(args.url, args.target))
        repo.save_backlink_audit(None, audit_res)

        print(f"\n--- Technical Backlink Audit Result ---")
        print(f"Link Found:        {'YES' if audit_res.link_found else 'NO'}")
        print(f"Dofollow Status:   {'DOFOLLOW (Equity Transferred)' if audit_res.is_dofollow else 'NOFOLLOW / RESTRICTED'}")
        print(f"Rel Attribute:     '{audit_res.rel_attribute or 'dofollow'}'")
        print(f"Anchor Text:       '{audit_res.anchor_text}'")
        print(f"Primary Keyword:   {'DETECTED' if audit_res.has_primary_keyword else 'NOT FOUND'}")
        print(f"Robots Indexable:  {audit_res.meta_robots}")
        print(f"Canonical URL:     {audit_res.canonical_url or 'Self-referencing / Default'}")
        print(f"TTFB Latency:      {audit_res.ttfb_ms} ms")
        print(f"Quality Score:     {audit_res.quality_score} / 100")
        if audit_res.issues:
            print("Audit Issues / Warnings:")
            for issue in audit_res.issues:
                print(f"  - {issue}")

    elif args.command == "hard-dry-test":
        from hard_dry_test import run_hard_dry_test

        asyncio.run(
            run_hard_dry_test(
                count=args.count,
                headless=args.headless,
                slow_mo=args.slow_mo,
            )
        )

    elif args.command == "check-serp":
        from automation.serp_tracker import SERPTracker
        print(f"Checking organic SERP rankings for keyword: '{args.keyword}'...")
        print(f"Target domain: {args.domain}")
        tracker = SERPTracker(target_domain=args.domain)
        result = asyncio.run(tracker.check_keyword(args.keyword))
        repo.record_serp_ranking(
            result.keyword, result.search_engine, result.rank_position,
            result.found_url, result.page_title, result.snippet
        )
        print("\n--- Organic SERP Tracking Result ---")
        if result.is_ranked:
            print(f"Position:     Rank #{result.rank_position} (PAGE ONE/TOP RESULTS)")
            print(f"Found URL:    {result.found_url}")
            print(f"Page Title:   {result.page_title}")
        else:
            print(f"Position:     Not currently in top {result.total_results_checked} organic results.")

    elif args.command == "check-health":
        from platforms.health_checker import PlatformHealthChecker
        checker = PlatformHealthChecker(timeout_seconds=settings.health_check_timeout)
        if args.domain:
            targets = [{"domain": args.domain, "submission_url": f"https://{args.domain}"}]
        else:
            targets = [dict(r) for r in repo.platforms()]
        print(f"Checking availability & latency for {len(targets)} platform(s)...")
        results = asyncio.run(checker.check_batch(targets))
        for res in results:
            repo.record_platform_health(
                None, res.domain, res.is_reachable, res.status_code,
                res.latency_ms, res.ssl_valid, res.error_message
            )
            status_icon = "✓ ONLINE" if res.is_reachable else "✗ OFFLINE"
            print(f"[{status_icon}] {res.domain} | HTTP {res.status_code} | Latency: {res.latency_ms}ms" + (f" ({res.error_message})" if res.error_message else ""))

    elif args.command == "test-notification":
        from notifications.notifier import WebhookNotifier
        notifier = WebhookNotifier(settings, repo)
        print(f"Dispatching test alert notification...")
        print(f"Webhook URL: {settings.webhook_url or 'None configured (simulated mode)'}")
        success = asyncio.run(notifier.notify("TEST_ALERT", "Innovions System Alert", args.message))
        print(f"Notification status: {'SUCCESS' if success else 'FAILED'}")


if __name__ == "__main__":
    main()
