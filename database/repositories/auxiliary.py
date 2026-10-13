"""Auxiliary domain repository classes for accounts, health, SERP, content evaluation, public verification, and analytics."""
from __future__ import annotations

import sqlite3
from typing import Any
from ..connection import transaction
from . import BaseRepository, now


class AccountRepository(BaseRepository):
    """Persistence operations for accounts and persistent session states."""

    def upsert_account(
        self,
        domain: str,
        username: str,
        password: str,
        storage_state_path: str | None = None,
    ) -> int:
        clean_domain = domain.strip().lower().removeprefix("www.")
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO accounts (domain, username, password, storage_state_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    username = excluded.username,
                    password = excluded.password,
                    storage_state_path = COALESCE(excluded.storage_state_path, accounts.storage_state_path)
                """,
                (clean_domain, username, password, storage_state_path, ts),
            )
            return cur.lastrowid

    def get_account(self, domain: str) -> sqlite3.Row | None:
        clean_domain = domain.strip().lower().removeprefix("www.")
        return self.db.execute("SELECT * FROM accounts WHERE domain = ?", (clean_domain,)).fetchone()

    def update_account_session(self, domain: str, storage_state_path: str) -> None:
        clean_domain = domain.strip().lower().removeprefix("www.")
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                "UPDATE accounts SET storage_state_path = ?, last_login_at = ? WHERE domain = ?",
                (storage_state_path, ts, clean_domain),
            )


class HealthRepository(BaseRepository):
    """Persistence operations for platform availability, SSL health, and latency."""

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
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO platform_health (
                    platform_id, domain, is_reachable, status_code,
                    latency_ms, ssl_valid, error_message, checked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    platform_id,
                    domain,
                    1 if is_reachable else 0,
                    status_code,
                    latency_ms,
                    1 if ssl_valid else 0,
                    error_message,
                    ts,
                ),
            )
            return cur.lastrowid

    def get_platform_health(self, domain: str | None = None) -> list[sqlite3.Row]:
        if domain:
            clean_d = domain.strip().lower().removeprefix("www.")
            return self.db.execute("SELECT * FROM platform_health WHERE domain = ? ORDER BY id DESC", (clean_d,)).fetchall()
        return self.db.execute("SELECT * FROM platform_health ORDER BY id DESC").fetchall()


class SerpRepository(BaseRepository):
    """Persistence operations for SERP keyword rankings."""

    def record_serp_ranking(
        self,
        keyword: str,
        search_engine: str,
        rank_position: int | None,
        found_url: str | None = None,
        page_title: str | None = None,
        snippet: str | None = None,
    ) -> int:
        ts = now()
        prev = self.db.execute(
            "SELECT rank_position FROM serp_rankings WHERE keyword = ? AND search_engine = ? ORDER BY id DESC LIMIT 1",
            (keyword, search_engine),
        ).fetchone()

        rank_delta = 0
        if prev and prev["rank_position"] and rank_position:
            rank_delta = prev["rank_position"] - rank_position

        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO serp_rankings (
                    keyword, search_engine, rank_position, rank_delta,
                    found_url, page_title, snippet, checked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (keyword, search_engine, rank_position, rank_delta, found_url, page_title, snippet, ts),
            )
            return cur.lastrowid

    def get_serp_rankings(self, keyword: str | None = None) -> list[sqlite3.Row]:
        if keyword:
            return self.db.execute("SELECT * FROM serp_rankings WHERE keyword = ? ORDER BY id DESC", (keyword,)).fetchall()
        return self.db.execute("SELECT * FROM serp_rankings ORDER BY id DESC").fetchall()

    def get_latest_serp_rankings(self) -> list[sqlite3.Row]:
        return self.db.execute(
            """
            SELECT * FROM serp_rankings
            WHERE id IN (SELECT MAX(id) FROM serp_rankings GROUP BY keyword)
            ORDER BY keyword ASC
            """
        ).fetchall()


class ContentEvaluationRepository(BaseRepository):
    """Persistence operations for content quality and semantic evaluations."""

    def record_content_evaluation(self, draft_id: int | None, platform_id: int | None, evaluation: Any) -> int:
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO content_evaluations (
                    draft_id, platform_id, relevance_score, accuracy_score,
                    readability_score, safety_score, composite_score, grade,
                    auto_approved, justification, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    platform_id,
                    evaluation.relevance_score,
                    evaluation.accuracy_score,
                    evaluation.readability_score,
                    evaluation.safety_score,
                    evaluation.composite_score,
                    evaluation.grade,
                    1 if evaluation.auto_approved else 0,
                    evaluation.justification,
                    ts,
                ),
            )
            return cur.lastrowid

    def get_content_evaluations(self, draft_id: int | None = None) -> list[sqlite3.Row]:
        if draft_id is not None:
            return self.db.execute("SELECT * FROM content_evaluations WHERE draft_id = ? ORDER BY id DESC", (draft_id,)).fetchall()
        return self.db.execute("SELECT * FROM content_evaluations ORDER BY id DESC").fetchall()


class PublicVerificationRepository(BaseRepository):
    """Persistence operations for unauthenticated public post and link verifications."""

    def record_public_verification(self, submission_id: int | None, platform_id: int | None, verif_result: Any) -> int:
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO public_verifications (
                    submission_id, platform_id, published_url, is_publicly_visible,
                    public_link_verified, destination_http_code, moderation_status,
                    details, verified_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission_id,
                    platform_id,
                    verif_result.published_url,
                    1 if verif_result.is_publicly_visible else 0,
                    1 if verif_result.public_link_verified else 0,
                    verif_result.destination_http_code,
                    verif_result.moderation_status,
                    verif_result.details,
                    ts,
                ),
            )
            return cur.lastrowid

    def get_public_verifications(self, platform_id: int | None = None) -> list[sqlite3.Row]:
        if platform_id is not None:
            return self.db.execute("SELECT * FROM public_verifications WHERE platform_id = ? ORDER BY id DESC", (platform_id,)).fetchall()
        return self.db.execute("SELECT * FROM public_verifications ORDER BY id DESC").fetchall()


class CampaignAnalyticsRepository(BaseRepository):
    """Persistence operations for UTM attribution and estimated traffic analytics."""

    def record_campaign_analytics(
        self,
        platform_id: int | None,
        domain: str,
        utm_url: str,
        traffic_tier: str = "Medium",
        estimated_impressions: int = 0,
        equity_value_score: float = 0.0,
    ) -> int:
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO campaign_analytics (
                    platform_id, domain, utm_url, traffic_tier,
                    estimated_monthly_impressions, equity_value_score, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (platform_id, domain, utm_url, traffic_tier, estimated_impressions, equity_value_score, ts),
            )
            return cur.lastrowid

    def get_campaign_analytics(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM campaign_analytics ORDER BY id DESC").fetchall()


class NotificationRepository(BaseRepository):
    """Persistence operations for outbound webhook and alert notifications."""

    def record_notification(
        self,
        event_type: str,
        channel: str,
        message: str,
        status: str,
        payload: str | None = None,
    ) -> int:
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO notification_logs (event_type, channel, message, payload, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_type, channel, message, payload, status, ts),
            )
            return cur.lastrowid

    def get_notifications(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM notification_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
