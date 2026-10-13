"""Unified SQLite Repository facade combining focused domain repositories."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .connection import get_db_connection, transaction
from .migrations import MigrationRunner
from .repositories import (
    PlatformRepository,
    DraftRepository,
    SubmissionRepository,
    AuditRepository,
    now,
)
from .repositories.auxiliary import (
    AccountRepository,
    HealthRepository,
    SerpRepository,
    ContentEvaluationRepository,
    PublicVerificationRepository,
    CampaignAnalyticsRepository,
    NotificationRepository,
)


class Repository:
    """Unified persistence facade for Innovions SEO Social Bookmarking Automation.
    
    Delegates to focused domain repositories while preserving 100% backward compatibility
    for all public interfaces, existing CLI commands, and test suites.
    """

    def __init__(self, path: Path | str, auto_migrate: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db: sqlite3.Connection = get_db_connection(self.path)

        # Initialize focused domain repositories
        self._platforms = PlatformRepository(self.db)
        self._drafts = DraftRepository(self.db)
        self._submissions = SubmissionRepository(self.db)
        self._audits = AuditRepository(self.db)
        self._accounts = AccountRepository(self.db)
        self._health = HealthRepository(self.db)
        self._serp = SerpRepository(self.db)
        self._evaluations = ContentEvaluationRepository(self.db)
        self._verifications = PublicVerificationRepository(self.db)
        self._analytics = CampaignAnalyticsRepository(self.db)
        self._notifications = NotificationRepository(self.db)

        if auto_migrate:
            self._init_db()

    def _init_db(self) -> None:
        """Applies baseline schema and versioned migrations."""
        runner = MigrationRunner(self.path)
        runner.apply_all(create_backup=False)

    # --- Platforms ---
    def upsert_platform(self, item: dict) -> int:
        return self._platforms.upsert_platform(item)

    def platforms(self, statuses: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        return self._platforms.platforms(statuses)

    def get_platform(self, platform_id_or_domain: int | str) -> sqlite3.Row | None:
        return self._platforms.get_platform(platform_id_or_domain)

    def set_metrics(
        self,
        platform_id: int,
        metrics: dict[str, Any],
        status: str,
        reason: str | None = None,
    ) -> None:
        self._platforms.set_metrics(platform_id, metrics, status, reason)

    def cleanup_legacy_rows(self) -> int:
        return self._platforms.cleanup_legacy_rows()

    # --- Drafts ---
    def save_draft(
        self,
        platform_id: int,
        title: str,
        description: str,
        target_url: str,
        tags: str = "",
        valid: bool = False,
    ) -> int:
        return self._drafts.save_draft(platform_id, title, description, target_url, tags, valid)

    def update_draft_content(
        self,
        platform_id: int,
        title: str,
        description: str,
        tags: str = "",
        approved: bool | None = None,
    ) -> None:
        self._drafts.update_draft_content(platform_id, title, description, tags, approved)

    def draft_for(self, platform_id: int) -> sqlite3.Row | None:
        return self._drafts.draft_for(platform_id)

    def approve_draft(self, platform_id: int, approved: bool) -> None:
        self._drafts.approve_draft(platform_id, approved)

    # --- Submissions ---
    def record_submission(
        self,
        platform_id: int,
        draft_id: int | None,
        target_url: str,
        status: str,
        published_url: str | None = None,
        error_message: str | None = None,
        screenshot_path: str | None = None,
    ) -> int:
        return self._submissions.record_submission(
            platform_id, draft_id, target_url, status, published_url, error_message, screenshot_path
        )

    def submitted(self, platform_id: int, target_url: str) -> bool:
        return self._submissions.submitted(platform_id, target_url)

    def submissions(self) -> list[sqlite3.Row]:
        return self._submissions.submissions()

    # --- Audits ---
    def save_backlink_audit(self, platform_id: int | None, audit_res) -> int:
        return self._audits.save_backlink_audit(platform_id, audit_res)

    def get_backlink_audits(self, platform_id: int | None = None) -> list[sqlite3.Row]:
        return self._audits.get_backlink_audits(platform_id)

    def get_audit_summary(self) -> dict:
        return self._audits.get_audit_summary()

    def save_site_seo_audit(self, data: dict) -> int:
        return self._audits.save_site_seo_audit(data)

    def get_latest_site_seo_audit(self, target_url: str | None = None) -> sqlite3.Row | None:
        return self._audits.get_latest_site_seo_audit(target_url)

    # --- Accounts & Sessions ---
    def upsert_account(
        self,
        domain: str,
        username: str,
        password: str,
        storage_state_path: str | None = None,
    ) -> int:
        return self._accounts.upsert_account(domain, username, password, storage_state_path)

    def get_account(self, domain: str) -> sqlite3.Row | None:
        return self._accounts.get_account(domain)

    def update_account_session(self, domain: str, storage_state_path: str) -> None:
        self._accounts.update_account_session(domain, storage_state_path)

    # --- Platform Health ---
    def record_platform_health(
        self,
        platform_id: int | None,
        domain: str,
        is_reachable: bool,
        status_code: int = 0,
        latency_ms: float = 0.0,
        ssl_valid: bool = True,
        error_message: str | None = None,
    ) -> int:
        return self._health.record_platform_health(
            platform_id, domain, is_reachable, status_code, latency_ms, ssl_valid, error_message
        )

    def get_platform_health(self, domain: str | None = None) -> list[sqlite3.Row]:
        return self._health.get_platform_health(domain)

    # --- Workflow State ---
    def save_workflow_state(self, key: str, value: str) -> None:
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO workflow_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, ts),
            )

    def get_workflow_state(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM workflow_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    # --- SERP Rankings ---
    def record_serp_ranking(
        self,
        keyword: str,
        search_engine: str,
        rank_position: int | None,
        found_url: str | None = None,
        page_title: str | None = None,
        snippet: str | None = None,
    ) -> int:
        return self._serp.record_serp_ranking(keyword, search_engine, rank_position, found_url, page_title, snippet)

    def get_serp_rankings(self, keyword: str | None = None) -> list[sqlite3.Row]:
        return self._serp.get_serp_rankings(keyword)

    def get_latest_serp_rankings(self) -> list[sqlite3.Row]:
        return self._serp.get_latest_serp_rankings()

    # --- Content Evaluations ---
    def record_content_evaluation(self, draft_id: int | None, platform_id: int | None, evaluation: Any) -> int:
        return self._evaluations.record_content_evaluation(draft_id, platform_id, evaluation)

    def get_content_evaluations(self, draft_id: int | None = None) -> list[sqlite3.Row]:
        return self._evaluations.get_content_evaluations(draft_id)

    # --- Public Verifications ---
    def record_public_verification(self, submission_id: int | None, platform_id: int | None, verif_result: Any) -> int:
        return self._verifications.record_public_verification(submission_id, platform_id, verif_result)

    def get_public_verifications(self, platform_id: int | None = None) -> list[sqlite3.Row]:
        return self._verifications.get_public_verifications(platform_id)

    # --- Campaign Analytics ---
    def record_campaign_analytics(
        self,
        platform_id: int | None,
        domain: str,
        utm_url: str,
        traffic_tier: str = "Medium",
        estimated_impressions: int = 0,
        equity_value_score: float = 0.0,
    ) -> int:
        return self._analytics.record_campaign_analytics(
            platform_id, domain, utm_url, traffic_tier, estimated_impressions, equity_value_score
        )

    def get_campaign_analytics(self) -> list[sqlite3.Row]:
        return self._analytics.get_campaign_analytics()

    # --- Notifications ---
    def record_notification(
        self,
        event_type: str,
        channel: str,
        message: str,
        status: str = "DELIVERED",
        payload: str | None = None,
    ) -> int:
        return self._notifications.record_notification(event_type, channel, message, status, payload)

    def get_notifications(self, limit: int = 50) -> list[sqlite3.Row]:
        return self._notifications.get_notifications(limit)

    def get_notification_logs(self, limit: int = 50) -> list[sqlite3.Row]:
        return self._notifications.get_notifications(limit)

    def close(self) -> None:
        """Closes the underlying SQLite database connection."""
        self.db.close()
