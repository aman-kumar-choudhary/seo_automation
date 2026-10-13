"""Submission orchestrator executing the 18-step visible browser workflow."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from database.models import Status, Draft, ApprovalStatus
from platforms.adapters.supported_platforms import get_adapter
from automation.verification import SubmissionResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from config import Settings
    from database.repository import Repository
    from automation.browser import VisibleBrowser
    from automation.controller import WorkflowController, Monitor


class SubmissionOrchestrator:
    """Executes the strict 18-step Playwright submission workflow for a single platform."""

    def __init__(
        self,
        settings: Settings,
        repo: Repository,
        browser: VisibleBrowser,
        monitor: Monitor,
        controller: WorkflowController,
    ):
        self.settings = settings
        self.repo = repo
        self.browser = browser
        self.monitor = monitor
        self.controller = controller

    async def execute(self, platform_row: dict) -> SubmissionResult:
        platform_row = dict(platform_row)
        platform_id = platform_row["id"]
        platform_name = platform_row["name"]
        domain = platform_row["domain"]
        target_url = self.settings.target_url
        sub_url = platform_row.get("submission_url") or f"https://{domain}"

        # 1. Display platform name and current status
        await self.monitor.log(f"Starting submission workflow for {platform_name} ({domain}).")
        await self.monitor.state(
            operation={
                "platform_id": platform_id,
                "current_platform_name": platform_name,
                "current_website_url": sub_url,
                "workflow_stage": "PREPARING_SUBMISSION",
                "browser_action": "Initializing platform workflow",
                "current_target_url": target_url,
                "eligibility_status": "ELIGIBLE",
            }
        )

        # Retrieve or verify platform adapter
        adapter = get_adapter(domain)
        if not adapter:
            msg = f"No verified platform adapter available for domain '{domain}'. Manual review required."
            await self.monitor.log(msg)
            self.repo.set_metrics(platform_id, {}, Status.REJECTED, msg)
            return SubmissionResult(success=False, status=Status.REJECTED, error_message=msg)

        # 2. Navigate to the platform in visible browser
        await self.monitor.log(f"Navigating to {sub_url} in visible browser...")
        try:
            await self.browser.goto(sub_url, timeout=30000)
        except Exception as exc:
            err = f"Failed to navigate to {sub_url}: {exc}"
            await self.monitor.log(err)
            err_shot = await self.browser.screenshot(f"nav_error_{domain}")
            self.repo.record_submission(platform_id, None, target_url, Status.FAILED, error_message=err, screenshot_path=err_shot)
            return SubmissionResult(success=False, status=Status.FAILED, error_message=err, screenshot_path=err_shot)

        # 3. Confirm that the website loaded successfully
        if not self.browser.page:
            return SubmissionResult(success=False, status=Status.FAILED, error_message="Browser page not loaded")

        # 4. Display the current URL in the dashboard
        current_url = self.browser.page.url
        await self.monitor.state(operation={"current_website_url": current_url, "browser_action": "Page loaded"})

        # 5. Check authentication status and auto-login if credentials exist
        await self.monitor.log(f"Checking authentication status on {platform_name}...")
        is_auth, auth_issue = await adapter.check_auth(self.browser)
        if not is_auth:
            # Check if stored credentials exist for domain and attempt auto-login
            creds = self.browser.account_mgr.get_credentials(domain)
            if creds:
                await self.monitor.log(f"Auto-login: Stored credentials detected for {domain}. Attempting automated login...")
                login_ok, login_err = await self.browser.account_mgr.auto_login(self.browser, domain)
                if login_ok:
                    await self.monitor.log(f"Auto-login succeeded for {domain}! Persistent session saved.")
                    is_auth, _ = await adapter.check_auth(self.browser)
                else:
                    await self.monitor.log(f"Auto-login attempt failed on {domain}: {login_err}")

        if not is_auth:
            issue_msg = auth_issue or "Authentication or human verification required."
            await self.monitor.log(f"Manual intervention needed on {platform_name}: {issue_msg}")
            await self.monitor.state(intervention=issue_msg, operation={"workflow_stage": "MANUAL_INTERVENTION_REQUIRED"})
            
            # Wait safely for user to complete manual authentication in the visible window
            while not is_auth and await self.controller.checkpoint():
                if self.controller.skip:
                    self.controller.skip = False
                    await self.monitor.log(f"Skipping {platform_name} on operator request.")
                    await self.monitor.state(intervention=None)
                    return SubmissionResult(success=False, status=Status.SKIPPED, error_message="Skipped during authentication")
                await asyncio.sleep(1.0)
                is_auth, _ = await adapter.check_auth(self.browser)

            await self.monitor.state(intervention=None)
            await self.monitor.log(f"Authentication confirmed for {platform_name}.")
            # Save session for future runs
            if self.browser.context:
                await self.browser.account_mgr.save_session_state(self.browser.context, domain)

        if not await self.controller.checkpoint():
            return SubmissionResult(success=False, status=Status.SKIPPED, error_message="Stopped by operator")

        # 7. Navigate to the appropriate submission form
        await self.monitor.log(f"Navigating to submission form on {platform_name}...")
        await self.monitor.state(operation={"workflow_stage": "NAVIGATING_FORM", "browser_action": "Finding submission form"})
        form_ready = await adapter.navigate_to_form(self.browser)
        if not form_ready:
            # Fallback: attempt deep form discovery and click modal triggers
            from automation.form_detector import IntelligentFormDetector
            form_detector = IntelligentFormDetector()
            form_ready = await form_detector.discover_and_open_form(self.browser)

        if not form_ready:
            err = f"Submission form could not be located on {platform_name}"
            await self.monitor.log(err)
            err_shot = await self.browser.screenshot(f"form_missing_{domain}")
            self.repo.record_submission(platform_id, None, target_url, Status.FAILED, error_message=err, screenshot_path=err_shot)
            return SubmissionResult(success=False, status=Status.FAILED, error_message=err, screenshot_path=err_shot)

        # 8. Identify required fields & 9/10/11. Fill title, description, target URL, tags
        draft_row = self.repo.draft_for(platform_id)
        if not draft_row:
            return SubmissionResult(success=False, status=Status.FAILED, error_message="No draft found in database")

        draft = Draft(
            title=draft_row["title"],
            description=draft_row["description"],
            target_url=draft_row["target_url"],
            tags=draft_row["tags"] or "",
            valid=bool(draft_row["valid"]),
            approval_status=draft_row["approval_status"],
        )

        # Autonomous Content Quality & Relevance Review
        if self.settings.auto_content_evaluation:
            try:
                from content.evaluator import ContentEvaluator
                evaluator = ContentEvaluator(self.settings.keyword, self.settings.min_content_approval_score)
                eval_res = evaluator.evaluate_draft(draft, target_url)
                self.repo.record_content_evaluation(draft_row["id"], platform_id, eval_res)
                await self.monitor.log(f"Autonomous Content Review: Grade {eval_res.grade} ({eval_res.composite_score}/100) — {eval_res.justification}")
                if eval_res.auto_approved:
                    self.repo.approve_draft(platform_id, True)
                    draft.approval_status = ApprovalStatus.APPROVED
            except Exception as eval_err:
                logger.warning("Content evaluation error: %s", eval_err)

        await self.monitor.log(f"Populating submission form with visible DOM highlighting...")
        await self.monitor.state(
            operation={
                "workflow_stage": "POPULATING_FORM",
                "browser_action": "Populating form fields",
                "current_submission_title": draft.title,
            }
        )

        # Inject client-side autofill helper
        try:
            from automation.form_detector import IntelligentFormDetector
            form_detector = IntelligentFormDetector()
            if self.browser.page:
                await form_detector.inject_autofill_helper(self.browser.page, draft)
        except Exception:
            pass

        fill_ok, fill_err = await adapter.fill_form(self.browser, draft)
        if not fill_ok:
            err = f"Form population failed on {platform_name}: {fill_err}"
            await self.monitor.log(err)
            err_shot = await self.browser.screenshot(f"fill_failed_{domain}")
            self.repo.record_submission(platform_id, draft_row["id"], target_url, Status.FAILED, error_message=err, screenshot_path=err_shot)
            return SubmissionResult(success=False, status=Status.FAILED, error_message=err, screenshot_path=err_shot)

        # 12. Display completed draft for review & capture 'before' screenshot
        before_shot = await self.browser.screenshot_mgr.capture_before_submission(self.browser.page, platform_name)
        await self.monitor.log(f"Pre-submission screenshot saved: {before_shot}")
        await self.monitor.state(
            last_screenshot=before_shot,
            operation={"workflow_stage": "AWAITING_APPROVAL", "browser_action": "Form populated; awaiting approval"},
            draft={
                "title": draft.title,
                "description": draft.description,
                "target_url": draft.target_url,
                "tags": draft.tags,
                "approval_status": draft.approval_status,
            },
        )

        # 13. Wait for approval if manual approval is enabled
        if self.settings.manual_approval:
            await self.monitor.log(f"Waiting for operator approval for {platform_name}...")
            while await self.controller.checkpoint():
                if self.controller.skip:
                    self.controller.skip = False
                    await self.monitor.log(f"Platform {platform_name} skipped by operator.")
                    self.repo.record_submission(platform_id, draft_row["id"], target_url, Status.SKIPPED, error_message="Skipped during approval")
                    return SubmissionResult(success=False, status=Status.SKIPPED)

                # Check if draft updated or approved in DB
                curr_draft = self.repo.draft_for(platform_id)
                if curr_draft and curr_draft["approval_status"] == ApprovalStatus.APPROVED:
                    await self.monitor.log("Operator approved submission.")
                    break
                elif curr_draft and curr_draft["approval_status"] == ApprovalStatus.REJECTED:
                    await self.monitor.log("Operator rejected submission.")
                    self.repo.record_submission(platform_id, draft_row["id"], target_url, Status.REJECTED, error_message="Rejected by operator")
                    return SubmissionResult(success=False, status=Status.REJECTED)

                await asyncio.sleep(0.3)

        if not await self.controller.checkpoint():
            return SubmissionResult(success=False, status=Status.SKIPPED, error_message="Workflow stopped")

        # 14. Publish only after the required approval. Dry-run mode blocks publishing!
        if self.settings.dry_run:
            msg = "Dry-run mode is ACTIVE: Form validated and populated successfully, but publication button was NOT clicked."
            await self.monitor.log(msg)
            self.repo.record_submission(
                platform_id,
                draft_row["id"],
                target_url,
                Status.AWAITING_APPROVAL,
                error_message="Dry-run completed; submission withheld",
                screenshot_path=before_shot,
            )
            return SubmissionResult(
                success=True,
                status=Status.AWAITING_APPROVAL,
                screenshot_path=before_shot,
            )

        # Perform actual publication
        await self.monitor.log(f"Submitting bookmark to {platform_name}...")
        await self.monitor.state(operation={"workflow_stage": "SUBMITTING", "browser_action": "Submitting form"})
        submitted = await adapter.submit(self.browser)
        if not submitted:
            err = f"Submit button could not be activated on {platform_name}"
            await self.monitor.log(err)
            err_shot = await self.browser.screenshot(f"submit_error_{domain}")
            self.repo.record_submission(platform_id, draft_row["id"], target_url, Status.FAILED, error_message=err, screenshot_path=err_shot)
            return SubmissionResult(success=False, status=Status.FAILED, error_message=err, screenshot_path=err_shot)

        # 15. Verify resulting page or platform confirmation
        await self.monitor.log(f"Verifying publication outcome on {platform_name}...")
        await self.monitor.state(operation={"workflow_stage": "VERIFYING_OUTCOME", "browser_action": "Verifying page result"})
        result = await adapter.verify(self.browser, sub_url, target_url)

        # 16. Record published URL and 17. Save screenshot & execution record
        after_shot = await self.browser.screenshot_mgr.capture_after_submission(self.browser.page, platform_name, result.success)
        result.screenshot_path = after_shot
        await self.monitor.state(last_screenshot=after_shot)

        if result.success:
            await self.monitor.log(f"Submission confirmed! Published URL: {result.published_url or 'Confirmed on page'}")
            sub_id = self.repo.record_submission(
                platform_id,
                draft_row["id"],
                target_url,
                Status.PUBLISHED,
                published_url=result.published_url,
                screenshot_path=after_shot,
            )
            self.repo.set_metrics(platform_id, {}, Status.PUBLISHED)

            # 1. Independent Public Post & Link Verification
            if self.settings.public_verification_enabled and result.published_url:
                try:
                    from automation.public_verifier import PublicPostVerifier
                    verifier = PublicPostVerifier(target_url=target_url)
                    verif_res = await verifier.verify_public_url(result.published_url)
                    self.repo.record_public_verification(sub_id, platform_id, verif_res)
                    badge = "CONFIRMED PUBLIC" if verif_res.is_publicly_visible else "NOT PUBLIC"
                    await self.monitor.log(
                        f"Independent Public Verification: [{badge}] "
                        f"Public Access={verif_res.is_publicly_visible} | Link Verified={verif_res.public_link_verified} | Status={verif_res.moderation_status}"
                    )
                except Exception as verif_err:
                    logger.warning("Public verification check error: %s", verif_err)

            # 2. Trigger live Technical SEO Backlink Audit
            audit_res = None
            try:
                from automation.seo_auditor import TechnicalSEOAuditor
                auditor = TechnicalSEOAuditor(primary_keyword=self.settings.keyword)
                audit_target_url = result.published_url or self.browser.page.url
                audit_res = await auditor.audit_url(audit_target_url, target_url, page=self.browser.page)
                self.repo.save_backlink_audit(platform_id, audit_res)
                await self.monitor.log(
                    f"Backlink audit completed: Grade={audit_res.indexability_grade} | Quality Score={audit_res.quality_score}/100 | "
                    f"Dofollow={audit_res.is_dofollow} | Anchor='{audit_res.anchor_text}' | "
                    f"Robots.txt={'ALLOWED' if audit_res.robots_txt_allowed else 'DISALLOWED'}"
                )
            except Exception as audit_err:
                logger.warning("Technical backlink audit error: %s", audit_err)

            # 3. Campaign Referral Traffic & Search Visibility Impact
            if self.settings.traffic_analytics_enabled and audit_res:
                try:
                    from automation.traffic_analytics import TrafficAnalyticsTracker
                    tracker = TrafficAnalyticsTracker(target_url=target_url)
                    analytics = tracker.estimate_platform_impact(
                        domain=domain,
                        da=platform_row.get("da") or 30.0,
                        is_dofollow=audit_res.is_dofollow,
                        quality_score=audit_res.quality_score,
                    )
                    self.repo.record_campaign_analytics(
                        platform_id, domain, analytics.utm_url,
                        analytics.traffic_tier, analytics.estimated_monthly_impressions,
                        analytics.equity_value_score,
                    )
                    await self.monitor.log(
                        f"Campaign Referral Impact: Tier='{analytics.traffic_tier}' | "
                        f"Est. Impressions={analytics.estimated_monthly_impressions}/mo | "
                        f"Equity Value=${analytics.equity_value_score:.2f} | UTM: {analytics.utm_url}"
                    )
                except Exception as tr_err:
                    logger.warning("Traffic analytics error: %s", tr_err)

        else:
            await self.monitor.log(f"Submission unverified or failed: {result.error_message}")
            self.repo.record_submission(
                platform_id,
                draft_row["id"],
                target_url,
                Status.FAILED,
                error_message=result.error_message,
                screenshot_path=after_shot,
            )
            self.repo.set_metrics(platform_id, {}, Status.FAILED, result.error_message)

        # 18. Update dashboard status
        await self.monitor.state(
            operation={
                "workflow_stage": "SUBMISSION_COMPLETED" if result.success else "SUBMISSION_FAILED",
                "browser_action": "Finished platform processing",
                "eligibility_status": "PUBLISHED" if result.success else "FAILED",
            },
            progress=self.controller.progress(),
        )

        return result
