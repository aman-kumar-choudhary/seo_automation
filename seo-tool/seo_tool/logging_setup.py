from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(getattr(record, "ctx", {}) or {})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> logging.Logger:
    root = logging.getLogger("seo_tool")
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level.upper())
    console.setFormatter(JsonFormatter())
    root.addHandler(console)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(JsonFormatter())
        root.addHandler(fh)
    return root


def log(logger: logging.Logger, level: int, msg: str, **ctx: Any) -> None:
    logger.log(level, msg, extra={"ctx": ctx})
