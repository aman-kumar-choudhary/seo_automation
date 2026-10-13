from __future__ import annotations

import asyncio
from datetime import datetime
from database.models import Status, ApprovalStatus
from platforms.discovery import discover
from platforms.metrics import MetricsProvider
from platforms.eligibility import decision
from content.generator import make_draft, validate
from automation.submission import SubmissionOrchestrator
from notifications.notifier import WebhookNotifier


class Monitor:
    """Helper for broadcasting formatted logs, state, and intervention banners."""

    def __init__(self, hub):
        self.hub = hub

    async def log(self, message: str) -> None:
        t = datetime.now().strftime("%H:%M:%S")
        print(f"[{t}] {message}", flush=True)
        await self.hub.emit("log", {"time": t, "message": message})

    async def state(self, **fields) -> None:
        await self.hub.emit("state", fields)

    async def set_intervention(self, message: str | None) -> None:
        await self.hub.emit("intervention", message)


class WorkflowController:
    """Manages the lifecycle of discovery, metrics verification, draft generation, and visible submissions."""

    def __init__(self, settings, repo, hub, browser):
        self.settings = settings
        self.repo = repo
        self.hub = hub
        self.browser = browser
        self.browser.controller = self
        self.monitor = Monitor(hub)
        self.notifier = WebhookNotifier(settings, repo)
        self.paused = False
        self.stopped = False
        self.skip = False
        self.running = False
        self.run_lock = asyncio.Lock()
        self.current_platform_id: int | None = None

    async def initialize(self) -> None:
        try:
            if hasattr(self.repo, "cleanup_legacy_rows"):
                self.repo.cleanup_legacy_rows()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).debug("Initialization cleanup skipped: %s", exc)
        await self.monitor.log("Dashboard ready. Click Start to begin the safe workflow.")
        await self.monitor.state(
            operation={
                "workflow_stage": "READY",
                "target_url": self.settings.target_url,
                "eligibility_status": "Awaiting operator start",
            },
            progress=self.progress(),
        )

    def progress(self) -> dict:
        rows = self.repo.platforms()
        statuses = [r["eligibility_status"] for r in rows]
        total = len(rows)
        evaluated = sum(s not in ("DISCOVERED",) for s in statuses)
        rejected = statuses.count(Status.REJECTED)
        eligible = statuses.count(Status.ELIGIBLE)
        completed = statuses.count(Status.PUBLISHED)
        awaiting = statuses.count(Status.AWAITING_APPROVAL)
        failed = statuses.count(Status.FAILED)
        pct = 0 if total == 0 else round((evaluated * 100) / total)

        return {
            "total_platforms_discovered": total,
            "platforms_evaluated": evaluated,
            "platforms_rejected": rejected,
            "platforms_eligible": eligible,
            "submissions_completed": completed,
            "submissions_awaiting_approval": awaiting,
            "failed_submissions": failed,
            "overall_progress_percentage": pct,
        }

    async def handle_commands(self) -> None:
        """Continuously processes operator commands, draft edit events, and quick-add platforms from dashboard."""
        while not self.stopped:
            try:
                cmd_task = asyncio.create_task(self.hub.commands.get())
                draft_task = asyncio.create_task(self.hub.draft_updates.get())
                add_task = asyncio.create_task(self.hub.platform_add_queue.get())
                done, pending = await asyncio.wait(
                    [cmd_task, draft_task, add_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=0.5,
                )

                for task in pending:
                    task.cancel()

                for task in done:
                    val = task.result()
                    if isinstance(val, str):
                        await self._process_command(val)
                    elif isinstance(val, dict):
                        await self._process_platform_add(val)
                    else:
                        await self._process_draft_update(val)
            except asyncio.TimeoutError:
                pass
            except Exception as exc:
                await asyncio.sleep(0.1)

    async def _process_platform_add(self, item: dict) -> None:
        """Processes dynamic platform addition from the dashboard Quick-Add bar."""
        pid = self.repo.upsert_platform(item)
        await self.monitor.log(f"Quick-Add: Platform '{item['name']}' ({item['domain']}) registered.")
        from platforms.metrics import MetricsProvider
        from platforms.eligibility import decision
        provider = MetricsProvider(self.settings)
        metrics = await provider.fetch(item["domain"])
        status, reason = decision(metrics, self.settings)
        self.repo.set_metrics(pid, metrics or {}, status, reason)
        await self.monitor.log(f"Quick-Add: Evaluated as [{status}] (DA: {metrics.get('da', '-')}, Spam: {metrics.get('spam_score', '-')}%).")
        await self.monitor.state(progress=self.progress())

    async def _process_command(self, command: str) -> None:
        if command == "start":
            if self.run_lock.locked() or self.running:
                await self.monitor.log("Workflow is already in progress. Ignoring duplicate start request.")
            else:
                asyncio.create_task(self.run())
        elif command == "pause":
            self.paused = True
            await self.monitor.log("Pause requested: workflow will pause safely at the next checkpoint.")
            await self.monitor.state(operation={"browser_action": "Workflow paused"})
        elif command == "resume":
            self.paused = False
            await self.monitor.log("Workflow resumed by operator.")
            await self.monitor.state(operation={"browser_action": "Workflow resumed"})
        elif command == "stop":
            self.stopped = True
            self.running = False
            await self.monitor.log("Stop requested: workflow safely terminated and progress preserved.")
            await self.monitor.state(operation={"workflow_stage": "STOPPED", "browser_action": "Stopped"})
        elif command == "skip":
            self.skip = True
            await self.monitor.log("Current platform will be skipped safely at next step.")
        elif command == "approve":
            await self.approve(True)
        elif command == "reject":
            await self.approve(False)
        elif command == "screenshot" and self.browser.page:
            path = await self.browser.screenshot("manual")
            await self.monitor.log(f"Manual screenshot saved: {path}")
        elif command == "open" and self.browser.page:
            await self.monitor.log(f"Current visible URL: {self.browser.page.url}")
        elif command == "toggle_continuous":
            self.continuous_mode = not self.continuous_mode
            status_str = "ENABLED (Continuous auto-search active)" if self.continuous_mode else "DISABLED"
            await self.monitor.log(f"Continuous Auto-Task mode {status_str}.")
            await self.monitor.state(continuous_mode=self.continuous_mode)
        elif command == "toggle_auto_approval":
            self.settings.manual_approval = not self.settings.manual_approval
            status_str = "DISABLED (Full auto-pilot active)" if not self.settings.manual_approval else "ENABLED (Manual review required)"
            await self.monitor.log(f"Manual approval gate {status_str}.")
            await self.monitor.state(manual_approval=self.settings.manual_approval)

    async def _process_draft_update(self, update_req) -> None:
        pid = update_req.platform_id or self.current_platform_id
        if pid:
            self.repo.update_draft_content(
                pid,
                update_req.title,
                update_req.description,
                update_req.tags,
                approved=True if update_req.approve else None,
            )
            await self.monitor.log(f"Draft updated by operator." + (" Approved for submission." if update_req.approve else ""))
            draft = self.repo.draft_for(pid)
            if draft:
                await self.monitor.state(
                    draft={
                        "title": draft["title"],
                        "description": draft["description"],
                        "target_url": draft["target_url"],
                        "tags": draft["tags"],
                        "approval_status": draft["approval_status"],
                    }
                )

    async def checkpoint(self) -> bool:
        """Safe execution checkpoint. Pauses safely when pause is requested."""
        if self.stopped:
            return False
        if self.paused:
            await self.monitor.log("Execution paused at safe checkpoint. Waiting for Resume...")
            while self.paused and not self.stopped:
                await asyncio.sleep(0.3)
        return not self.stopped

    async def approve(self, approved: bool) -> None:
        pid = self.current_platform_id or self.hub.state.get("operation", {}).get("platform_id")
        if pid:
            self.repo.approve_draft(pid, approved)
            status_text = "APPROVED" if approved else "REJECTED"
            await self.monitor.log(f"Draft for platform ID {pid} {status_text} by operator.")
            draft = self.repo.draft_for(pid)
            if draft:
                await self.monitor.state(
                    draft={
                        "title": draft["title"],
                        "description": draft["description"],
                        "target_url": draft["target_url"],
                        "tags": draft["tags"],
                        "approval_status": status_text,
                    }
                )

    async def run(self) -> None:
        """Executes the automated workflow with concurrency locking and bounded continuous cycles."""
        if self.run_lock.locked() or self.running:
            await self.monitor.log("Workflow is already in progress. Ignoring duplicate start request.")
            return

        async with self.run_lock:
            await self._run_internal()

    async def _run_internal(self) -> None:
        self.running = True
        self.stopped = False
        self.continuous_mode = getattr(self, "continuous_mode", self.settings.continuous)
        max_cycles = getattr(self.settings, "max_continuous_cycles", 5)
        cycle = 1

        try:
            while not self.stopped:
                if self.continuous_mode and cycle > max_cycles:
                    await self.monitor.log(f"Continuous mode: configured cycle limit ({max_cycles}) reached. Concluding safely.")
                    break

                await self.monitor.log(f"=== [CYCLE {cycle}] Starting Automated Social Media SEO Workflow ===")

                # 0. SERP Ranking Position Check (if enabled)
                if self.settings.serp_tracking_enabled:
                    try:
                        from automation.serp_tracker import SERPTracker
                        serp = SERPTracker(target_domain="innovions.org")
                        rank_res = await serp.check_keyword(self.settings.keyword)
                        self.repo.record_serp_ranking(
                            rank_res.keyword,
                            rank_res.search_engine,
                            rank_res.rank_position,
                            rank_res.found_url,
                            rank_res.page_title,
                            rank_res.snippet,
                        )
                        r_display = f"#{rank_res.rank_position}" if rank_res.is_ranked else "Not in top 30"
                        await self.monitor.log(f"SERP Tracker: Keyword '{self.settings.keyword}' organic position -> {r_display}")
                    except Exception as serp_err:
                        import logging
                        logging.getLogger(__name__).warning("SERP tracking warning: %s", serp_err)

                # 1. Platform Discovery & Active Web Search
                await self.monitor.log(f"[Phase 1] Auto-searching web for social media SEO platforms...")
                await self.monitor.state(
                    operation={"workflow_stage": "AUTO_SEARCHING_WEB", "browser_action": "Scanning web for candidate platforms"}
                )
                count = await discover(self.repo, self.settings)
                await self.monitor.log(f"Discovery scan complete: {count} unique platforms in directory.")
                await self.monitor.state(progress=self.progress())

                if not await self.checkpoint():
                    return

                # 2. SEO Metric Validation
                await self.monitor.log("[Phase 2] Verifying SEO metrics and domain authority...")
                provider = MetricsProvider(self.settings)
                all_platforms = self.repo.platforms()

                for row in all_platforms:
                    if not await self.checkpoint():
                        return

                    row = dict(row)
                    domain = row["domain"]
                    # Skip already published platforms or explicitly rejected platforms
                    if row.get("eligibility_status") in (Status.PUBLISHED, Status.REJECTED):
                        continue
                    # Skip already ELIGIBLE platforms if they already have verified metrics
                    if row.get("eligibility_status") == Status.ELIGIBLE and row.get("da") is not None:
                        continue

                    await self.monitor.state(
                        operation={
                            "platform_id": row["id"],
                            "current_platform_name": row["name"],
                            "current_website_url": row["submission_url"],
                            "workflow_stage": "METRIC_VERIFICATION",
                            "browser_action": f"Verifying authority metrics for {domain}",
                            "target_url": self.settings.target_url,
                        }
                    )

                    metrics = await provider.fetch(domain)
                    status, reason = decision(metrics, self.settings)
                    self.repo.set_metrics(row["id"], metrics or {}, status, reason)

                    await self.monitor.state(
                        metrics={
                            "DA": None if not metrics else metrics.get("da"),
                            "PA": None if not metrics else metrics.get("pa"),
                            "Spam Score": None if not metrics else metrics.get("spam_score"),
                            "Metric provider": None if not metrics else metrics.get("provider"),
                            "Eligibility": status,
                            "Reason": reason,
                        },
                        progress=self.progress(),
                    )
                    await self.monitor.log(f"{row['name']} ({domain}): {status}" + (f" — {reason}" if reason else ""))

                # 3. Content Generation & Submissions for ELIGIBLE platforms
                target_statuses = (Status.ELIGIBLE, Status.AWAITING_APPROVAL) if not self.settings.manual_approval else (Status.ELIGIBLE,)
                eligible_rows = self.repo.platforms(target_statuses)
                await self.monitor.log(f"[Phase 3] Processing {len(eligible_rows)} eligible platform(s)...")

                orchestrator = SubmissionOrchestrator(
                    self.settings,
                    self.repo,
                    self.browser,
                    self.monitor,
                    self,
                )

                processed_count = 0
                for row in eligible_rows:
                    if not await self.checkpoint():
                        return

                    row = dict(row)
                    if self.settings.run_limit is not None and processed_count >= self.settings.run_limit:
                        await self.monitor.log(f"Configured submission limit ({self.settings.run_limit}) reached.")
                        break

                    self.current_platform_id = row["id"]
                    domain = row["domain"]

                    # Prevent duplicate submissions if already published
                    if self.repo.submitted(row["id"], self.settings.target_url):
                        continue

                    if self.skip:
                        self.skip = False
                        self.repo.set_metrics(row["id"], {}, Status.SKIPPED, "Skipped by operator")
                        await self.monitor.log(f"Platform {row['name']} skipped.")
                        continue

                    # Pre-screen domain availability and network latency
                    try:
                        from platforms.health_checker import PlatformHealthChecker
                        health_checker = PlatformHealthChecker(timeout_seconds=self.settings.health_check_timeout)
                        h_stat = await health_checker.check_platform(domain, row.get("submission_url"))
                        self.repo.record_platform_health(
                            row["id"], domain, h_stat.is_reachable, h_stat.status_code,
                            h_stat.latency_ms, h_stat.ssl_valid, h_stat.error_message
                        )
                        if not h_stat.is_reachable:
                            await self.monitor.log(f"Pre-screen: {domain} is unreachable ({h_stat.error_message}). Skipping safely.")
                            continue
                    except Exception as health_err:
                        import logging
                        logging.getLogger(__name__).warning("Pre-screen health check exception for %s: %s", domain, health_err)

                    # Generate content draft
                    draft = make_draft(row["name"], self.settings.keyword, self.settings.target_url, domain)
                    is_valid, val_reason = validate(draft, self.settings.keyword, self.settings.target_url)
                    if not is_valid:
                        await self.monitor.log(f"Draft validation failed for {row['name']}: {val_reason}")
                        continue

                    self.repo.save_draft(row["id"], draft.title, draft.description, draft.target_url, draft.tags, is_valid)
                    
                    # Auto-approve draft if manual approval is disabled
                    if not self.settings.manual_approval:
                        self.repo.approve_draft(row["id"], True)
                        self.repo.set_metrics(row["id"], {}, Status.AWAITING_APPROVAL)
                    else:
                        self.repo.set_metrics(row["id"], {}, Status.AWAITING_APPROVAL)

                    await self.monitor.state(
                        operation={
                            "platform_id": row["id"],
                            "current_platform_name": row["name"],
                            "workflow_stage": "DRAFT_PREPARED",
                            "current_submission_title": draft.title,
                            "eligibility_status": "AWAITING_APPROVAL",
                        },
                        draft={
                            "title": draft.title,
                            "description": draft.description,
                            "target_url": draft.target_url,
                            "tags": draft.tags,
                            "approval_status": "APPROVED" if not self.settings.manual_approval else "PENDING",
                        },
                        progress=self.progress(),
                    )
                    await self.monitor.log(f"Draft prepared for {row['name']}. Keyword '{self.settings.keyword}' validated.")

                    # Execute visible browser submission workflow
                    try:
                        result = await orchestrator.execute(dict(row))
                        processed_count += 1
                        if result.success and result.published_url:
                            await self.notifier.notify_published(row["name"], result.published_url)
                    except Exception as exc:
                        err_msg = f"Unexpected failure on {row['name']}: {type(exc).__name__}: {exc}"
                        await self.monitor.log(err_msg)
                        if self.browser.page:
                            err_shot = await self.browser.screenshot(f"crash_{domain}")
                            self.repo.record_submission(row["id"], None, self.settings.target_url, Status.FAILED, error_message=err_msg, screenshot_path=err_shot)
                        self.repo.set_metrics(row["id"], {}, Status.FAILED, err_msg)

                    await self.monitor.state(progress=self.progress())

                await self.monitor.log(f"=== [CYCLE {cycle}] Execution cycle completed. ===")
                await self.notifier.notify_cycle_completed(cycle, self.progress()["submissions_completed"])

                # If not continuous mode, finish
                if not self.continuous_mode:
                    break

                cycle += 1
                await self.monitor.log(
                    f"🔁 [CONTINUOUS AUTO-TASK] Active. Auto-searching more websites in {self.settings.loop_interval_seconds}s... (Click Stop anytime to end)"
                )
                for _ in range(self.settings.loop_interval_seconds):
                    if not await self.checkpoint():
                        return
                    await asyncio.sleep(1.0)

        except Exception as exc:
            await self.monitor.log(f"Workflow fatal error: {type(exc).__name__}: {exc}")
        finally:
            self.running = False
            self.current_platform_id = None
            await self.monitor.state(
                operation={"workflow_stage": "IDLE", "browser_action": "Workflow paused/finished"},
                progress=self.progress(),
            )
