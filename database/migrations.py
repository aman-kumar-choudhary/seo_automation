"""Database migration engine with automated backup and transactional execution."""
from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .connection import get_db_connection, transaction

logger = logging.getLogger(__name__)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def backup_database(db_path: Path | str) -> Path | None:
    """Creates a timestamped backup copy of the database before running schema changes."""
    path = Path(db_path)
    if not path.exists():
        return None
    backup_path = path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(path, backup_path)
    logger.info("Created pre-migration database backup at: %s", backup_path)
    return backup_path


class MigrationRunner:
    """Manages versioned schema migrations ensuring existing data preservation."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.schema_file = Path(__file__).parent / "schema.sql"

    def apply_all(self, create_backup: bool = True) -> int:
        """Applies baseline schema and all incremental migrations inside atomic transactions."""
        if create_backup and self.db_path.exists():
            backup_database(self.db_path)

        conn = get_db_connection(self.db_path)
        try:
            self._ensure_migrations_table(conn)
            self._apply_baseline(conn)
            applied_count = self._run_incremental_migrations(conn)
            return applied_count
        finally:
            conn.close()

    def _ensure_migrations_table(self, conn: sqlite3.Connection) -> None:
        with transaction(conn) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT UNIQUE NOT NULL,
                    description TEXT,
                    applied_at TEXT NOT NULL
                );
                """
            )

    def _apply_baseline(self, conn: sqlite3.Connection) -> None:
        """Applies baseline schema if not already initialized."""
        if not self.schema_file.exists():
            return

        with transaction(conn) as cur:
            cur.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = '000_baseline'")
            if cur.fetchone()[0] == 0:
                schema_sql = self.schema_file.read_text(encoding="utf-8")
                conn.executescript(schema_sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?)",
                    ("000_baseline", "Baseline database schema", now()),
                )
                logger.info("Applied baseline database schema.")

    def _run_incremental_migrations(self, conn: sqlite3.Connection) -> int:
        """Runs incremental migrations idempotently."""
        migrations = [
            ("001_platform_columns", "Add audit and restriction columns to platforms", self._m001_platform_columns),
            ("002_draft_updated_at", "Add updated_at column to drafts", self._m002_draft_updated_at),
            ("003_audit_columns", "Add canonical and robots columns to backlink audits", self._m003_audit_columns),
            ("004_serp_delta", "Add rank_delta column to serp_rankings", self._m004_serp_delta),
            ("005_site_seo_audits", "Add site_seo_audits table for technical crawler", self._m005_site_seo_audits),
        ]

        applied = 0
        for version, desc, func in migrations:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = ?", (version,))
            if cur.fetchone()[0] == 0:
                logger.info("Applying migration %s: %s", version, desc)
                with transaction(conn) as tx_cur:
                    func(conn, tx_cur)
                    tx_cur.execute(
                        "INSERT INTO schema_migrations (version, description, applied_at) VALUES (?, ?, ?)",
                        (version, desc, now()),
                    )
                applied += 1
            cur.close()

        return applied

    def _m001_platform_columns(self, conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
        cur.execute("PRAGMA table_info(platforms)")
        existing = {row["name"] for row in cur.fetchall()}
        cols = {
            "registration_requirements": "TEXT",
            "link_attributes": "TEXT",
            "public_visibility": "TEXT",
            "posting_restrictions": "TEXT",
        }
        for name, col_type in cols.items():
            if name not in existing:
                cur.execute(f"ALTER TABLE platforms ADD COLUMN {name} {col_type}")

    def _m002_draft_updated_at(self, conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
        cur.execute("PRAGMA table_info(drafts)")
        existing = {row["name"] for row in cur.fetchall()}
        if "updated_at" not in existing:
            cur.execute("ALTER TABLE drafts ADD COLUMN updated_at TEXT")

    def _m003_audit_columns(self, conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
        cur.execute("PRAGMA table_info(backlink_audits)")
        existing = {row["name"] for row in cur.fetchall()}
        cols = {
            "canonical_matched": "INTEGER DEFAULT 1",
            "robots_txt_allowed": "INTEGER DEFAULT 1",
            "indexability_grade": "TEXT DEFAULT 'A'",
        }
        for name, col_type in cols.items():
            if name not in existing:
                cur.execute(f"ALTER TABLE backlink_audits ADD COLUMN {name} {col_type}")

    def _m004_serp_delta(self, conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
        cur.execute("PRAGMA table_info(serp_rankings)")
        existing = {row["name"] for row in cur.fetchall()}
        if "rank_delta" not in existing:
            cur.execute("ALTER TABLE serp_rankings ADD COLUMN rank_delta INTEGER DEFAULT 0")

    def _m005_site_seo_audits(self, conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS site_seo_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_url TEXT NOT NULL,
                status_code INTEGER,
                ttfb_ms REAL,
                title TEXT,
                title_length INTEGER,
                title_issue TEXT,
                meta_description TEXT,
                meta_description_length INTEGER,
                meta_description_issue TEXT,
                h1_count INTEGER DEFAULT 0,
                h1_text TEXT,
                canonical_url TEXT,
                canonical_status TEXT,
                robots_meta TEXT,
                robots_txt_status TEXT,
                sitemap_url TEXT,
                sitemap_status TEXT,
                total_internal_links INTEGER DEFAULT 0,
                broken_internal_links INTEGER DEFAULT 0,
                total_images INTEGER DEFAULT 0,
                images_missing_alt INTEGER DEFAULT 0,
                structured_data_types TEXT,
                has_structured_data INTEGER DEFAULT 0,
                overall_seo_score INTEGER NOT NULL DEFAULT 0,
                issues_json TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
