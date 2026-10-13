"""SQLite database connection factory with foreign key enforcement and transactional context."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)


def get_db_connection(db_path: Path | str) -> sqlite3.Connection:
    """Creates a configured SQLite connection with foreign keys and WAL mode enabled."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Enforce SQLite foreign key constraints and performance pragmas
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except Exception as exc:
        logger.debug("Could not enable WAL mode: %s", exc)
    conn.execute("PRAGMA busy_timeout = 5000;")

    return conn


@contextmanager
def transaction(db: sqlite3.Connection) -> Generator[sqlite3.Cursor, None, None]:
    """Provides an atomic transaction block that commits on success or rolls back on exception."""
    cursor = db.cursor()
    try:
        yield cursor
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Transaction rolled back due to error: %s", exc)
        raise
    finally:
        cursor.close()
