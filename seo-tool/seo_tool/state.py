"""Crash-safe crawl checkpoints. Uses pickle, so only load state files you created yourself.
Checkpoints from a different tool version are ignored instead of crashing."""
from __future__ import annotations

import pickle
import sqlite3
import time
from pathlib import Path
from typing import Any

STATE_VERSION = 3


class CrawlState:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS snapshot (start_url TEXT PRIMARY KEY, saved_at REAL, data BLOB)")

    def save(self, start_url: str, payload: Any) -> None:
        blob = pickle.dumps((STATE_VERSION, payload), protocol=pickle.HIGHEST_PROTOCOL)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO snapshot VALUES (?, ?, ?)", (start_url, time.time(), blob))

    def load(self, start_url: str) -> Any | None:
        row = self.db.execute("SELECT data FROM snapshot WHERE start_url = ?", (start_url,)).fetchone()
        if not row:
            return None
        try:
            version, payload = pickle.loads(row[0])
        except Exception:
            return None
        return payload if version == STATE_VERSION else None

    def clear(self, start_url: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM snapshot WHERE start_url = ?", (start_url,))

    def close(self) -> None:
        self.db.close()
