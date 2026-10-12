from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    """Configuration settings for Innovions SEO Social Bookmarking Automation."""
    website: str = "https://innovions.org/"
    keyword: str = "RFID"
    database_path: Path = Path(os.getenv("SEO_DATABASE_PATH", "data/innovions.db"))
    dashboard_host: str = os.getenv("SEO_DASHBOARD_HOST", "127.0.0.1")
    dashboard_port: int = int(os.getenv("SEO_DASHBOARD_PORT", "8765"))
    headless: bool = os.getenv("SEO_HEADLESS", "false").lower() == "true"
    slow_mo: int = int(os.getenv("SEO_SLOW_MO", "300"))
    dry_run: bool = os.getenv("SEO_DRY_RUN", "true").lower() == "true"
    manual_approval: bool = os.getenv("SEO_MANUAL_APPROVAL", "true").lower() == "true"
    keep_browser_open: bool = os.getenv("SEO_KEEP_BROWSER_OPEN", "false").lower() == "true"
    min_da: int = Field(default=20, ge=0)
    min_pa: int = Field(default=15, ge=0)
    max_spam_score: float = Field(default=10.0, ge=0.0)
    run_limit: int | None = None
    screenshot_dir: Path = Path(os.getenv("SEO_SCREENSHOT_DIR", "screenshots"))
    trace_dir: Path = Path(os.getenv("SEO_TRACE_DIR", "traces"))
    output_dir: Path = Path(os.getenv("SEO_OUTPUT_DIR", "output"))

    # Metrics provider settings
    moz_api_url: str | None = os.getenv("MOZ_API_URL") or None
    moz_api_token: str | None = os.getenv("MOZ_API_TOKEN") or None
    auto_evaluate_fallback: bool = os.getenv("SEO_AUTO_EVALUATE_FALLBACK", "true").lower() == "true"

    # Search and Discovery settings
    search_api_url: str | None = os.getenv("SEO_SEARCH_API_URL") or None
    search_api_token: str | None = os.getenv("SEO_SEARCH_API_TOKEN") or None
    auto_search_web: bool = os.getenv("SEO_AUTO_SEARCH_WEB", "true").lower() == "true"
    discovery_max_results: int = int(os.getenv("SEO_DISCOVERY_MAX_RESULTS", "50"))

    # Continuous Auto Task settings ("never stops" loop)
    continuous: bool = os.getenv("SEO_CONTINUOUS", "false").lower() == "true"
    loop_interval_seconds: int = int(os.getenv("SEO_LOOP_INTERVAL", "30"))

    # Network Resilience and Throttling
    submission_cooldown_seconds: float = float(os.getenv("SEO_SUBMISSION_COOLDOWN", "1.5"))
    max_retries_per_platform: int = int(os.getenv("SEO_MAX_RETRIES", "3"))
    health_check_timeout: float = float(os.getenv("SEO_HEALTH_TIMEOUT", "6.0"))

    # Notifications & Webhook alerts
    webhook_url: str | None = os.getenv("SEO_WEBHOOK_URL") or None
    webhook_enabled: bool = os.getenv("SEO_WEBHOOK_ENABLED", "false").lower() == "true"

    # SERP Ranking Tracker
    serp_tracking_enabled: bool = os.getenv("SEO_SERP_TRACKING", "true").lower() == "true"

    @property
    def target_url(self) -> str:
        return self.website
