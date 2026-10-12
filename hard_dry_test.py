#!/usr/bin/env python3
"""Automated Hard Dry Test across N Social Media SEO Bookmarking Websites."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
import uvicorn
import httpx

from config import Settings
from database.repository import Repository
from database.models import Status, ApprovalStatus
from dashboard.app import EventHub, create_app
from automation.browser import VisibleBrowser
from automation.controller import WorkflowController
from automation.submission import SubmissionOrchestrator
from platforms.discovery import normalize
from platforms.metrics import MetricsProvider
from platforms.eligibility import decision
from platforms.test_platforms_server import create_test_server, PLATFORM_DEFINITIONS
from content.generator import make_draft, validate
from reports.report_generator import export, generate_summary


async def run_hard_dry_test(
    count: int = 5,
    headless: bool = False,
    slow_mo: int = 300,
    dashboard_port: int = 8765,
    test_server_port: int = 8766,
    db_path: str = "data/hard_dry_test.db",
):
    display_val = os.environ.get("DISPLAY", ":0")
    browser_desc = "HEADLESS" if headless else f"VISIBLE CHROMIUM (DISPLAY={display_val}, slow_mo={slow_mo}ms)"
    print("=" * 80)
    print(" 🚀 INNOVIONS SEO AUTOMATION: FULL HARD DRY TEST (MULTI-PLATFORM)")
    print(f" Target Website : https://innovions.org/")
    print(f" Primary Keyword: RFID")
    print(f" Website Count  : {count} Social Media SEO Platforms")
    print(f" Browser Mode   : {browser_desc}")
    print(f" Dry Run Mode   : ACTIVE (Hard Guarantee: Form filled & validated; publishing blocked)")
    print("=" * 80)

    # 1. Start the Multi-Platform Test Server
    test_app, selected_platforms = create_test_server(count=count, host="127.0.0.1", port=test_server_port)
    test_server_config = uvicorn.Config(
        test_app,
        host="127.0.0.1",
        port=test_server_port,
        log_level="warning",
    )
    test_server = uvicorn.Server(test_server_config)
    test_server_task = asyncio.create_task(test_server.serve())

    # Wait for test server to be ready
    while not test_server.started:
        await asyncio.sleep(0.05)
    print(f"✓ Social Media SEO Test Platforms Server live at: http://127.0.0.1:{test_server_port}")

    # 2. Setup Repository and Clean Database
    Path(db_path).unlink(missing_ok=True)
    repo = Repository(Path(db_path))

    # 3. Setup Settings
    settings = Settings(
        database_path=Path(db_path),
        dashboard_port=dashboard_port,
        headless=headless,
        slow_mo=slow_mo,
        dry_run=True,
        manual_approval=False,  # Auto-approve for automated end-to-end dry test
        moz_api_url=f"http://127.0.0.1:{test_server_port}/metrics",
        moz_api_token="test-authorized-token",
    )

    # 4. Start Live Dashboard Server
    hub = EventHub()
    dash_app = create_app(hub, settings.screenshot_dir)
    dash_config = uvicorn.Config(
        dash_app,
        host="127.0.0.1",
        port=dashboard_port,
        log_level="warning",
    )
    dash_server = uvicorn.Server(dash_config)
    dash_server_task = asyncio.create_task(dash_server.serve())

    while not dash_server.started:
        await asyncio.sleep(0.05)
    print(f"✓ Live Monitoring Dashboard live at: http://127.0.0.1:{dashboard_port}")

    # 5. Initialize Browser and Controller
    browser = VisibleBrowser(settings, None)
    controller = WorkflowController(settings, repo, hub, browser)
    browser.monitor = controller.monitor

    try:
        # Launch browser
        await browser.start()
        print(f"✓ Browser window launched successfully.")

        # Navigate to Innovions target site
        await browser.goto(settings.target_url)

        # Open dashboard tab
        await browser.open_dashboard(f"http://127.0.0.1:{dashboard_port}")
        await controller.initialize()

        # 6. Catalog the N Social Media SEO Platforms
        print(f"\n[PHASE 1] Cataloging {count} Social Media SEO Platforms...")
        for p in selected_platforms:
            sub_url = f"http://127.0.0.1:{test_server_port}/platform/{p['id']}"
            item = {
                "name": p["name"],
                "domain": p["domain"],
                "registration_url": sub_url,
                "submission_url": sub_url,
                "relevance": p["tagline"],
                "terms_url": f"{sub_url}#terms",
                "registration_requirements": "Pre-verified operator credentials",
                "link_attributes": "rel='nofollow' / verified social bookmark",
                "public_visibility": "Publicly indexable",
                "posting_restrictions": "RFID & technology relevance required",
                "available": True,
            }
            repo.upsert_platform(item)
            await controller.monitor.log(f"Discovered Social SEO Platform: {p['name']} ({p['domain']})")

        # 7. SEO Metric Verification
        print(f"\n[PHASE 2] Verifying SEO Metrics via Authorized Provider...")
        provider = MetricsProvider(settings)
        all_platforms = repo.platforms()

        for row in all_platforms:
            domain = row["domain"]
            values = await provider.fetch(domain)
            status, reason = decision(values, settings)
            repo.set_metrics(row["id"], values or {}, status, reason)
            metrics_str = f"DA: {values['da']} | PA: {values['pa']} | Spam: {values['spam_score']}%"
            await controller.monitor.log(f"{row['name']} -> {status} ({metrics_str})")
            await controller.monitor.state(
                metrics={
                    "DA": values["da"],
                    "PA": values["pa"],
                    "Spam Score": values["spam_score"],
                    "Metric provider": values["provider"],
                    "Eligibility": status,
                    "Reason": reason,
                },
                progress=controller.progress(),
            )

        # 8. Content Generation & Validation
        print(f"\n[PHASE 3] Generating Platform-Specific SEO Content for 'RFID'...")
        eligible_platforms = repo.platforms((Status.ELIGIBLE,))
        for row in eligible_platforms:
            draft = make_draft(row["name"], settings.keyword, settings.target_url, row["domain"])
            valid, reason = validate(draft, settings.keyword, settings.target_url)
            assert valid, f"Draft validation error: {reason}"
            repo.save_draft(row["id"], draft.title, draft.description, draft.target_url, draft.tags, valid)
            repo.approve_draft(row["id"], True)  # Pre-approved for automated dry-run testing
            await controller.monitor.log(f"Draft generated & validated for {row['name']}: '{draft.title}'")

        # 9. Automated Visible Browser Submissions (Hard Dry-Run)
        print(f"\n[PHASE 4] Executing 18-Step Visible Browser Workflow across all {len(eligible_platforms)} platforms...")
        orchestrator = SubmissionOrchestrator(settings, repo, browser, controller.monitor, controller)

        results = []
        for idx, row in enumerate(eligible_platforms, 1):
            print(f"\n--- [{idx}/{len(eligible_platforms)}] Automating Platform: {row['name']} ---")
            res = await orchestrator.execute(dict(row))
            results.append((row["name"], res))
            await asyncio.sleep(0.5)

        # 10. Generate Final Report
        report_file = Path("output/hard_dry_test_report.csv")
        export(repo, output_dir=report_file.parent)
        summary = generate_summary(repo)

        # 11. Final Summary Display
        print("\n" + "=" * 80)
        print(" 🎯 HARD DRY TEST COMPLETE: EXECUTIVE SUMMARY")
        print("=" * 80)
        print(f"Total Platforms Processed: {len(results)}")
        for name, r in results:
            status_text = "DRY-RUN VERIFIED (Publish blocked safely)" if r.status == Status.AWAITING_APPROVAL else str(r.status)
            print(f" • {name:<26} | Status: {status_text:<38} | Screenshot: {Path(r.screenshot_path or '').name}")

        print(f"\nExecution Report saved to: {report_file}")
        print(f"Eligibility Breakdown   : {summary['eligibility_breakdown']}")
        print(f"Submission Breakdown    : {summary['submission_breakdown']}")
        print(f"Playwright Traces saved : traces/session.zip")
        print("=" * 80)

    finally:
        print("\nTearing down browser, dashboard, and test platform servers...")
        await browser.close()
        dash_server.should_exit = True
        test_server.should_exit = True
        await asyncio.gather(dash_server_task, test_server_task, return_exceptions=True)
        print("✓ All test servers cleanly shutdown.")


def main():
    parser = argparse.ArgumentParser(description="Innovions SEO Hard Dry Test")
    parser.add_argument("--count", "-n", type=int, default=5, help="Number of Social Media SEO platforms to automate (default: 5)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (default: headed visible Chromium)")
    parser.add_argument("--slow-mo", type=int, default=300, help="Playwright slow_mo delay in milliseconds (default: 300)")
    parser.add_argument("--port", type=int, default=8765, help="Monitoring dashboard port (default: 8765)")
    parser.add_argument("--test-port", type=int, default=8766, help="Test platforms server port (default: 8766)")
    parser.add_argument("--db", type=str, default="data/hard_dry_test.db", help="Test database path")
    args = parser.parse_args()

    asyncio.run(
        run_hard_dry_test(
            count=args.count,
            headless=args.headless,
            slow_mo=args.slow_mo,
            dashboard_port=args.port,
            test_server_port=args.test_port,
            db_path=args.db,
        )
    )


if __name__ == "__main__":
    main()
