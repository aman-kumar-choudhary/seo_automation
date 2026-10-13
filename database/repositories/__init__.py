"""Focused domain repository classes for the Innovions persistence layer."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from ..connection import transaction
from ..models import Status, ApprovalStatus


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseRepository:
    """Base repository class providing common connection and query helpers."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db


class PlatformRepository(BaseRepository):
    """Persistence operations for candidate and registered platforms."""

    def upsert_platform(self, item: dict) -> int:
        ts = now()
        domain = item["domain"].strip().lower().removeprefix("www.")
        fields = {
            "name": item.get("name") or domain,
            "domain": domain,
            "registration_url": item.get("registration_url") or f"https://{domain}",
            "submission_url": item.get("submission_url") or f"https://{domain}",
            "relevance": item.get("relevance") or "Discovered candidate — policy review required",
            "terms_url": item.get("terms_url") or "",
            "registration_requirements": item.get("registration_requirements") or "Standard registration",
            "link_attributes": item.get("link_attributes") or "rel='nofollow' / verified social bookmark",
            "public_visibility": item.get("public_visibility") or "Publicly indexable",
            "posting_restrictions": item.get("posting_restrictions") or "Adhere to platform terms; avoid spam",
            "available": 1 if item.get("available", True) else 0,
            "created_at": ts,
            "updated_at": ts,
        }

        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO platforms (
                    name, domain, registration_url, submission_url, relevance, terms_url,
                    available, registration_requirements, link_attributes, public_visibility,
                    posting_restrictions, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    name = excluded.name,
                    submission_url = excluded.submission_url,
                    registration_url = excluded.registration_url,
                    relevance = excluded.relevance,
                    terms_url = excluded.terms_url,
                    available = excluded.available,
                    registration_requirements = COALESCE(excluded.registration_requirements, platforms.registration_requirements),
                    link_attributes = COALESCE(excluded.link_attributes, platforms.link_attributes),
                    public_visibility = COALESCE(excluded.public_visibility, platforms.public_visibility),
                    posting_restrictions = COALESCE(excluded.posting_restrictions, platforms.posting_restrictions),
                    updated_at = excluded.updated_at
                """,
                (
                    fields["name"],
                    fields["domain"],
                    fields["registration_url"],
                    fields["submission_url"],
                    fields["relevance"],
                    fields["terms_url"],
                    fields["available"],
                    fields["registration_requirements"],
                    fields["link_attributes"],
                    fields["public_visibility"],
                    fields["posting_restrictions"],
                    fields["created_at"],
                    fields["updated_at"],
                ),
            )
            return cur.lastrowid

    def platforms(self, statuses: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            return self.db.execute(
                f"SELECT * FROM platforms WHERE eligibility_status IN ({placeholders}) ORDER BY id ASC",
                statuses,
            ).fetchall()
        return self.db.execute("SELECT * FROM platforms ORDER BY id ASC").fetchall()

    def get_platform(self, platform_id_or_domain: int | str) -> sqlite3.Row | None:
        if isinstance(platform_id_or_domain, int):
            return self.db.execute("SELECT * FROM platforms WHERE id = ?", (platform_id_or_domain,)).fetchone()
        clean_d = str(platform_id_or_domain).strip().lower().removeprefix("www.")
        return self.db.execute("SELECT * FROM platforms WHERE domain = ?", (clean_d,)).fetchone()

    def set_metrics(
        self,
        platform_id: int,
        metrics: dict[str, Any],
        status: str,
        reason: str | None = None,
    ) -> None:
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                UPDATE platforms
                SET da = ?, pa = ?, spam_score = ?, metric_provider = ?,
                    metrics_verified_at = ?, eligibility_status = ?, rejection_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    metrics.get("da"),
                    metrics.get("pa"),
                    metrics.get("spam_score"),
                    metrics.get("provider"),
                    metrics.get("verified_at") or ts,
                    status,
                    reason,
                    ts,
                    platform_id,
                ),
            )

    def cleanup_legacy_rows(self) -> int:
        """Cleans up legacy Row representation strings safely in the persistence layer."""
        with transaction(self.db) as cur:
            cur.execute("UPDATE platforms SET eligibility_status = 'DISCOVERED' WHERE rejection_reason LIKE '%sqlite3.Row%'")
            return cur.rowcount


class DraftRepository(BaseRepository):
    """Persistence operations for SEO content drafts."""

    def save_draft(
        self,
        platform_id: int,
        title: str,
        description: str,
        target_url: str,
        tags: str = "",
        valid: bool = False,
    ) -> int:
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO drafts (platform_id, title, description, target_url, tags, valid, approval_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform_id, target_url) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    tags = excluded.tags,
                    valid = excluded.valid,
                    updated_at = excluded.updated_at
                """,
                (platform_id, title, description, target_url, tags, 1 if valid else 0, ApprovalStatus.PENDING, ts, ts),
            )
            return cur.lastrowid

    def update_draft_content(
        self,
        platform_id: int,
        title: str,
        description: str,
        tags: str = "",
        approved: bool | None = None,
    ) -> None:
        ts = now()
        app_status = ApprovalStatus.APPROVED if approved else (ApprovalStatus.REJECTED if approved is False else None)
        with transaction(self.db) as cur:
            if app_status:
                cur.execute(
                    "UPDATE drafts SET title = ?, description = ?, tags = ?, approval_status = ?, updated_at = ? WHERE platform_id = ?",
                    (title, description, tags, app_status, ts, platform_id),
                )
            else:
                cur.execute(
                    "UPDATE drafts SET title = ?, description = ?, tags = ?, updated_at = ? WHERE platform_id = ?",
                    (title, description, tags, ts, platform_id),
                )

    def draft_for(self, platform_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM drafts WHERE platform_id = ?", (platform_id,)).fetchone()

    def approve_draft(self, platform_id: int, approved: bool) -> None:
        val = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                "UPDATE drafts SET approval_status = ?, updated_at = ? WHERE platform_id = ?",
                (val, ts, platform_id),
            )


class SubmissionRepository(BaseRepository):
    """Persistence operations for bookmark submissions and records."""

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
        ts = now()
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO submissions (platform_id, draft_id, target_url, status, published_url, error_message, screenshot_path, retry_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(platform_id, target_url) DO UPDATE SET
                    status = excluded.status,
                    published_url = excluded.published_url,
                    error_message = excluded.error_message,
                    screenshot_path = excluded.screenshot_path,
                    retry_count = submissions.retry_count + 1,
                    updated_at = excluded.updated_at
                """,
                (platform_id, draft_id, target_url, status, published_url, error_message, screenshot_path, ts, ts),
            )
            return cur.lastrowid

    def submitted(self, platform_id: int, target_url: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM submissions WHERE platform_id = ? AND target_url = ? AND status = ?",
            (platform_id, target_url, Status.PUBLISHED),
        ).fetchone()
        return bool(row)

    def submissions(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM submissions ORDER BY id DESC").fetchall()


class AuditRepository(BaseRepository):
    """Persistence operations for backlink audits and technical site audits."""

    def save_backlink_audit(self, platform_id: int | None, audit_res) -> int:
        ts = now()
        issues_str = json.dumps(audit_res.issues) if audit_res.issues else "[]"
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO backlink_audits (
                    platform_id, published_url, target_url, link_found, is_dofollow,
                    rel_attribute, anchor_text, has_primary_keyword, meta_robots,
                    canonical_url, canonical_matched, robots_txt_allowed, status_code,
                    ttfb_ms, quality_score, indexability_grade, issues, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    platform_id,
                    audit_res.published_url,
                    audit_res.target_url,
                    1 if audit_res.link_found else 0,
                    1 if audit_res.is_dofollow else 0,
                    audit_res.rel_attribute,
                    audit_res.anchor_text,
                    1 if audit_res.has_primary_keyword else 0,
                    audit_res.meta_robots,
                    audit_res.canonical_url,
                    1 if getattr(audit_res, "canonical_matched", True) else 0,
                    1 if getattr(audit_res, "robots_txt_allowed", True) else 0,
                    audit_res.status_code,
                    audit_res.ttfb_ms,
                    audit_res.quality_score,
                    getattr(audit_res, "indexability_grade", "A"),
                    issues_str,
                    ts,
                ),
            )
            return cur.lastrowid

    def get_backlink_audits(self, platform_id: int | None = None) -> list[sqlite3.Row]:
        if platform_id is not None:
            return self.db.execute("SELECT * FROM backlink_audits WHERE platform_id = ? ORDER BY id DESC", (platform_id,)).fetchall()
        return self.db.execute("SELECT * FROM backlink_audits ORDER BY id DESC").fetchall()

    def get_audit_summary(self) -> dict:
        total = self.db.execute("SELECT COUNT(*) FROM backlink_audits").fetchone()[0]
        if total == 0:
            return {"total_audits": 0, "avg_quality_score": 0, "dofollow_ratio": 0}
        dofollow_count = self.db.execute("SELECT COUNT(*) FROM backlink_audits WHERE is_dofollow = 1").fetchone()[0]
        avg_score = self.db.execute("SELECT AVG(quality_score) FROM backlink_audits").fetchone()[0] or 0.0
        return {
            "total_audits": total,
            "avg_quality_score": round(avg_score, 1),
            "dofollow_ratio": round((dofollow_count * 100.0) / total, 1),
        }

    def save_site_seo_audit(self, data: dict) -> int:
        ts = now()
        issues_json = json.dumps(data.get("issues", []))
        types_str = ",".join(data.get("structured_data_types", []))
        with transaction(self.db) as cur:
            cur.execute(
                """
                INSERT INTO site_seo_audits (
                    target_url, status_code, ttfb_ms, title, title_length, title_issue,
                    meta_description, meta_description_length, meta_description_issue,
                    h1_count, h1_text, canonical_url, canonical_status, robots_meta,
                    robots_txt_status, sitemap_url, sitemap_status, total_internal_links,
                    broken_internal_links, total_images, images_missing_alt, structured_data_types,
                    has_structured_data, overall_seo_score, issues_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["target_url"],
                    data.get("status_code", 200),
                    data.get("ttfb_ms", 0.0),
                    data.get("title", ""),
                    data.get("title_length", 0),
                    data.get("title_issue", ""),
                    data.get("meta_description", ""),
                    data.get("meta_description_length", 0),
                    data.get("meta_description_issue", ""),
                    data.get("h1_count", 0),
                    data.get("h1_text", ""),
                    data.get("canonical_url", ""),
                    data.get("canonical_status", ""),
                    data.get("robots_meta", ""),
                    data.get("robots_txt_status", ""),
                    data.get("sitemap_url", ""),
                    data.get("sitemap_status", ""),
                    data.get("total_internal_links", 0),
                    data.get("broken_internal_links", 0),
                    data.get("total_images", 0),
                    data.get("images_missing_alt", 0),
                    types_str,
                    1 if data.get("has_structured_data") else 0,
                    data.get("overall_seo_score", 0),
                    issues_json,
                    ts,
                ),
            )
            return cur.lastrowid

    def get_latest_site_seo_audit(self, target_url: str | None = None) -> sqlite3.Row | None:
        if target_url:
            return self.db.execute("SELECT * FROM site_seo_audits WHERE target_url = ? ORDER BY id DESC LIMIT 1", (target_url,)).fetchone()
        return self.db.execute("SELECT * FROM site_seo_audits ORDER BY id DESC LIMIT 1").fetchone()
