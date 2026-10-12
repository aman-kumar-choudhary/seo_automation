from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .models import Status, ApprovalStatus


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    """SQLite repository for persistent storage of platforms, metrics, drafts, and submissions."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        self.db.executescript(schema)
        self._migrate_columns()
        self.db.commit()

    def _migrate_columns(self) -> None:
        """Ensures any recently added schema columns are present in existing databases."""
        cursor = self.db.cursor()
        cursor.execute("PRAGMA table_info(platforms)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        new_cols = {
            "registration_requirements": "TEXT",
            "link_attributes": "TEXT",
            "public_visibility": "TEXT",
            "posting_restrictions": "TEXT",
        }
        for col_name, col_type in new_cols.items():
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE platforms ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

        cursor.execute("PRAGMA table_info(drafts)")
        existing_draft_cols = {row["name"] for row in cursor.fetchall()}
        if "updated_at" not in existing_draft_cols:
            try:
                cursor.execute("ALTER TABLE drafts ADD COLUMN updated_at TEXT")
            except Exception:
                pass

        cursor.execute("PRAGMA table_info(platform_health)")
        health_info = {row["name"]: row["notnull"] for row in cursor.fetchall()}
        if health_info.get("platform_id") == 1:
            try:
                cursor.execute("CREATE TABLE platform_health_new (id INTEGER PRIMARY KEY AUTOINCREMENT, platform_id INTEGER, domain TEXT NOT NULL, is_reachable INTEGER NOT NULL DEFAULT 1, status_code INTEGER, latency_ms REAL, ssl_valid INTEGER DEFAULT 1, error_message TEXT, checked_at TEXT NOT NULL, FOREIGN KEY(platform_id) REFERENCES platforms(id))")
                cursor.execute("INSERT INTO platform_health_new SELECT * FROM platform_health")
                cursor.execute("DROP TABLE platform_health")
                cursor.execute("ALTER TABLE platform_health_new RENAME TO platform_health")
            except Exception:
                pass

    def upsert_platform(self, item: dict) -> int:
        """Inserts or updates a candidate platform deduplicated by normalized domain."""
        ts = now()
        domain = item["domain"].strip().lower()
        fields = {
            "name": item.get("name") or domain,
            "domain": domain,
            "registration_url": item.get("registration_url") or f"https://{domain}",
            "submission_url": item.get("submission_url") or f"https://{domain}",
            "relevance": item.get("relevance") or "Discovered candidate — policy review required",
            "terms_url": item.get("terms_url") or "",
            "available": 1 if item.get("available", True) else 0,
            "registration_requirements": item.get("registration_requirements") or "Standard account required",
            "link_attributes": item.get("link_attributes") or "rel='nofollow' / user-generated content",
            "public_visibility": item.get("public_visibility") or "Publicly indexable",
            "posting_restrictions": item.get("posting_restrictions") or "Follow platform terms; no spamming",
            "created_at": ts,
            "updated_at": ts,
        }
        sql = """
            INSERT INTO platforms(
                name, domain, registration_url, submission_url, relevance,
                terms_url, available, registration_requirements, link_attributes,
                public_visibility, posting_restrictions, created_at, updated_at
            )
            VALUES(
                :name, :domain, :registration_url, :submission_url, :relevance,
                :terms_url, :available, :registration_requirements, :link_attributes,
                :public_visibility, :posting_restrictions, :created_at, :updated_at
            )
            ON CONFLICT(domain) DO UPDATE SET
                name = excluded.name,
                registration_url = excluded.registration_url,
                submission_url = excluded.submission_url,
                relevance = excluded.relevance,
                terms_url = excluded.terms_url,
                available = excluded.available,
                registration_requirements = excluded.registration_requirements,
                link_attributes = excluded.link_attributes,
                public_visibility = excluded.public_visibility,
                posting_restrictions = excluded.posting_restrictions,
                updated_at = excluded.updated_at
        """
        self.db.execute(sql, fields)
        self.db.commit()
        row = self.db.execute("SELECT id FROM platforms WHERE domain = ?", (domain,)).fetchone()
        return row["id"]

    def get_platform(self, platform_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM platforms WHERE id = ?", (platform_id,)).fetchone()

    def platforms(self, statuses: tuple[str, ...] | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM platforms"
        args: tuple = ()
        if statuses:
            placeholders = ",".join("?" * len(statuses))
            sql += f" WHERE eligibility_status IN ({placeholders})"
            args = statuses
        sql += " ORDER BY id ASC"
        return self.db.execute(sql, args).fetchall()

    def set_metrics(
        self,
        platform_id: int,
        metrics: dict,
        status: Status | str,
        reason: str | None = None,
    ) -> None:
        ts = now()
        sql = """
            UPDATE platforms
            SET da = ?, pa = ?, spam_score = ?, metric_provider = ?,
                metrics_verified_at = ?, eligibility_status = ?, rejection_reason = ?,
                updated_at = ?
            WHERE id = ?
        """
        self.db.execute(
            sql,
            (
                metrics.get("da"),
                metrics.get("pa"),
                metrics.get("spam_score"),
                metrics.get("provider"),
                metrics.get("verified_at"),
                str(status),
                reason,
                ts,
                platform_id,
            ),
        )
        self.db.commit()

    def save_draft(
        self,
        platform_id: int,
        title: str,
        description: str,
        target_url: str,
        tags: str,
        valid: bool,
    ) -> int:
        ts = now()
        sql = """
            INSERT INTO drafts(platform_id, title, description, target_url, tags, valid, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform_id, target_url) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                tags = excluded.tags,
                valid = excluded.valid,
                updated_at = excluded.updated_at
        """
        self.db.execute(sql, (platform_id, title, description, target_url, tags, 1 if valid else 0, ts, ts))
        self.db.commit()
        row = self.db.execute(
            "SELECT id FROM drafts WHERE platform_id = ? AND target_url = ?",
            (platform_id, target_url),
        ).fetchone()
        return row["id"]

    def update_draft_content(
        self,
        platform_id: int,
        title: str,
        description: str,
        tags: str,
        approved: bool | None = None,
    ) -> None:
        ts = now()
        status_clause = ""
        params: list = [title, description, tags, ts]
        if approved is True:
            status_clause = ", approval_status = 'APPROVED'"
        elif approved is False:
            status_clause = ", approval_status = 'REJECTED'"
        sql = f"UPDATE drafts SET title = ?, description = ?, tags = ?, updated_at = ?{status_clause} WHERE platform_id = ?"
        params.append(platform_id)
        self.db.execute(sql, params)
        self.db.commit()

    def draft_for(self, platform_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM drafts WHERE platform_id = ?", (platform_id,)).fetchone()

    def approve_draft(self, platform_id: int, approved: bool) -> None:
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        ts = now()
        self.db.execute(
            "UPDATE drafts SET approval_status = ?, updated_at = ? WHERE platform_id = ?",
            (status, ts, platform_id),
        )
        self.db.commit()

    def submitted(self, platform_id: int, target_url: str) -> bool:
        """Returns True if this exact (platform_id, target_url) was already successfully PUBLISHED."""
        row = self.db.execute(
            "SELECT 1 FROM submissions WHERE platform_id = ? AND target_url = ? AND status = ?",
            (platform_id, target_url, Status.PUBLISHED),
        ).fetchone()
        return row is not None

    def record_submission(
        self,
        platform_id: int,
        draft_id: int | None,
        target_url: str,
        status: Status | str,
        **kwargs,
    ) -> None:
        ts = now()
        sql = """
            INSERT INTO submissions(
                platform_id, draft_id, target_url, status,
                published_url, error_message, screenshot_path, retry_count,
                created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform_id, target_url) DO UPDATE SET
                draft_id = excluded.draft_id,
                status = excluded.status,
                published_url = excluded.published_url,
                error_message = excluded.error_message,
                screenshot_path = excluded.screenshot_path,
                retry_count = submissions.retry_count + 1,
                updated_at = excluded.updated_at
        """
        self.db.execute(
            sql,
            (
                platform_id,
                draft_id,
                target_url,
                str(status),
                kwargs.get("published_url"),
                kwargs.get("error_message"),
                kwargs.get("screenshot_path"),
                kwargs.get("retry_count", 0),
                ts,
                ts,
            ),
        )
        self.db.commit()

    def save_workflow_state(self, key: str, value: str) -> None:
        ts = now()
        self.db.execute(
            "INSERT INTO workflow_state(key, value, updated_at) VALUES(?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, ts),
        )
        self.db.commit()

    def get_workflow_state(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM workflow_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def report_rows(self) -> list[sqlite3.Row]:
        sql = """
            SELECT
                p.id as platform_id,
                p.name as platform_name,
                p.domain,
                p.submission_url,
                p.da,
                p.pa,
                p.spam_score,
                p.metric_provider,
                p.metrics_verified_at,
                p.eligibility_status,
                p.rejection_reason,
                p.link_attributes,
                p.public_visibility,
                d.title as draft_title,
                d.description as draft_description,
                d.target_url,
                d.approval_status,
                s.status as submission_status,
                s.published_url,
                s.error_message,
                s.screenshot_path,
                s.updated_at as submitted_at
            FROM platforms p
            LEFT JOIN drafts d ON d.platform_id = p.id
            LEFT JOIN submissions s ON s.platform_id = p.id
            ORDER BY p.id ASC
        """
        return self.db.execute(sql).fetchall()

    def save_backlink_audit(self, platform_id: int | None, audit) -> int:
        """Persists a technical SEO backlink audit record."""
        ts = now()
        issues_json = json.dumps(audit.issues or [])
        cur = self.db.execute(
            """
            INSERT INTO backlink_audits(
                platform_id, published_url, target_url, link_found,
                is_dofollow, rel_attribute, anchor_text, has_primary_keyword,
                meta_robots, canonical_url, status_code, ttfb_ms,
                quality_score, issues, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                platform_id,
                audit.published_url,
                audit.target_url,
                1 if audit.link_found else 0,
                1 if audit.is_dofollow else 0,
                audit.rel_attribute,
                audit.anchor_text,
                1 if audit.has_primary_keyword else 0,
                audit.meta_robots,
                audit.canonical_url,
                audit.status_code,
                audit.ttfb_ms,
                audit.quality_score,
                issues_json,
                ts,
            ),
        )
        self.db.commit()
        return cur.lastrowid

    def get_backlink_audits(self, platform_id: int | None = None) -> list[sqlite3.Row]:
        """Returns all recorded backlink audits or audits for a specific platform."""
        if platform_id is not None:
            return self.db.execute(
                "SELECT * FROM backlink_audits WHERE platform_id = ? ORDER BY id DESC",
                (platform_id,),
            ).fetchall()
        return self.db.execute("SELECT * FROM backlink_audits ORDER BY id DESC").fetchall()

    def get_audit_summary(self) -> dict:
        """Returns aggregated backlink equity metrics."""
        rows = self.db.execute("SELECT * FROM backlink_audits").fetchall()
        if not rows:
            return {
                "total_audits": 0,
                "links_found": 0,
                "dofollow_count": 0,
                "dofollow_ratio": 0.0,
                "avg_quality_score": 0.0,
                "keyword_anchors": 0,
            }

        total = len(rows)
        found = sum(1 for r in rows if r["link_found"])
        dofollow = sum(1 for r in rows if r["is_dofollow"])
        kw_anchors = sum(1 for r in rows if r["has_primary_keyword"])
        avg_score = round(sum(r["quality_score"] for r in rows) / total, 1)
        ratio = round((dofollow / total) * 100, 1)

        return {
            "total_audits": total,
            "links_found": found,
            "dofollow_count": dofollow,
            "dofollow_ratio": ratio,
            "avg_quality_score": avg_score,
            "keyword_anchors": kw_anchors,
        }

    def record_platform_health(
        self,
        platform_id: int | None,
        domain: str,
        is_reachable: bool,
        status_code: int = 200,
        latency_ms: float = 0.0,
        ssl_valid: bool = True,
        error_message: str | None = None,
    ) -> int:
        """Records platform availability ping and latency metrics."""
        ts = now()
        cur = self.db.execute(
            """
            INSERT INTO platform_health(
                platform_id, domain, is_reachable, status_code,
                latency_ms, ssl_valid, error_message, checked_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
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
        self.db.commit()
        return cur.lastrowid

    def get_platform_health(self, domain: str | None = None) -> list[sqlite3.Row]:
        if domain:
            return self.db.execute(
                "SELECT * FROM platform_health WHERE domain = ? ORDER BY id DESC",
                (domain,),
            ).fetchall()
        return self.db.execute("SELECT * FROM platform_health ORDER BY id DESC").fetchall()

    def record_serp_ranking(
        self,
        keyword: str,
        search_engine: str,
        rank_position: int | None,
        found_url: str | None,
        page_title: str | None = None,
        snippet: str | None = None,
    ) -> int:
        """Records an organic SERP ranking check for a keyword."""
        ts = now()
        cur = self.db.execute(
            """
            INSERT INTO serp_rankings(
                keyword, search_engine, rank_position, found_url,
                page_title, snippet, checked_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                keyword,
                search_engine,
                rank_position,
                found_url,
                page_title,
                snippet,
                ts,
            ),
        )
        self.db.commit()
        return cur.lastrowid

    def get_latest_serp_rankings(self) -> list[sqlite3.Row]:
        """Returns the most recent SERP check for each keyword."""
        return self.db.execute(
            """
            SELECT * FROM serp_rankings
            WHERE id IN (SELECT MAX(id) FROM serp_rankings GROUP BY keyword)
            ORDER BY keyword ASC
            """
        ).fetchall()

    def record_notification(
        self,
        event_type: str,
        channel: str,
        message: str,
        payload: dict | None = None,
        status: str = "DELIVERED",
    ) -> int:
        """Logs an outbound webhook or alert notification."""
        ts = now()
        payload_json = json.dumps(payload or {})
        cur = self.db.execute(
            """
            INSERT INTO notification_logs(
                event_type, channel, message, payload, status, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (event_type, channel, message, payload_json, status, ts),
        )
        self.db.commit()
        return cur.lastrowid

    def get_notification_logs(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM notification_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
