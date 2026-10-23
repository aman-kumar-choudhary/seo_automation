"""Configuration: defaults < TOML file < SEO_* environment variables < CLI flags."""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

ENV_PREFIX = "SEO_"


@dataclass
class Config:
    max_pages: int = 200
    max_depth: int = 6
    crawl_delay: float = 1.0           # per-host seconds; robots.txt Crawl-delay wins if larger
    timeout: float = 15.0
    max_retries: int = 3
    backoff_base: float = 1.0
    max_backoff: float = 60.0
    max_response_bytes: int = 5_000_000
    user_agent: str = "ResponsibleSEOAudit/0.3 (+https://example.com/seo-bot)"
    # Disabled by default to prevent SSRF against localhost, private networks,
    # and cloud-metadata endpoints. Enable only in an isolated test environment.
    allow_private_networks: bool = False
    include_subdomains: bool = False
    strip_tracking_params: bool = True
    use_sitemap_seeds: bool = True
    check_external_links: bool = True
    max_link_checks: int = 150         # external links + non-HTML assets per run
    render_js: bool = False
    slow_response_seconds: float = 1.5
    target_keywords: list[str] = field(default_factory=list)
    output_dir: str = "seo_output"
    log_level: str = "INFO"
    # crawl-trap protection
    exclude_patterns: list[str] = field(default_factory=list)  # regexes; matching URLs are not crawled
    max_query_params: int = 5          # skip discovered URLs with more query params; 0 = no limit
    check_llms_txt: bool = True
    # resilience
    adaptive_throttle: bool = True
    breaker_threshold: int = 5
    breaker_cooldown: float = 120.0
    # Google data (0 = off)
    pagespeed_urls: int = 0
    pagespeed_strategy: str = "mobile"
    gsc_property: str = ""
    gsc_credentials_file: str = ""
    gsc_urls: int = 50
    # AI suggestions (API key only via env SEO_AI_API_KEY)
    ai_suggestions: bool = False
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = ""
    ai_max_pages: int = 20
    brand_voice: str = ""

    @classmethod
    def load(cls, path: str | None = None, overrides: dict[str, Any] | None = None) -> "Config":
        values: dict[str, Any] = {}
        if path:
            values.update(tomllib.loads(Path(path).read_text(encoding="utf-8")))
        for f in fields(cls):
            env = os.environ.get(ENV_PREFIX + f.name.upper())
            if env is not None:
                values[f.name] = env
        values.update({k: v for k, v in (overrides or {}).items() if v is not None})
        unknown = set(values) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown config keys: {', '.join(sorted(unknown))}")
        cfg = cls()
        for key, value in values.items():
            setattr(cfg, key, _coerce(value, getattr(cfg, key)))
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.max_pages < 1 or self.max_depth < 0:
            raise ValueError("max_pages must be >= 1 and max_depth >= 0")
        if self.crawl_delay < 0.5:
            raise ValueError("crawl_delay must be >= 0.5s (polite crawling is enforced)")
        if self.max_retries < 0 or self.timeout <= 0:
            raise ValueError("invalid retry/timeout settings")
        if not self.user_agent.strip():
            raise ValueError("user_agent must identify the crawler")
        if self.max_query_params < 0:
            raise ValueError("max_query_params must be >= 0")
        for pattern in self.exclude_patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid exclude pattern {pattern!r}: {exc}") from exc
        if self.pagespeed_strategy not in ("mobile", "desktop"):
            raise ValueError("pagespeed_strategy must be mobile or desktop")
        if self.breaker_threshold < 1 or self.breaker_cooldown <= 0:
            raise ValueError("invalid circuit breaker settings")
        if self.gsc_property and not self.gsc_credentials_file:
            raise ValueError("gsc_property requires gsc_credentials_file")
        if self.ai_suggestions and not self.ai_model:
            raise ValueError("ai_suggestions requires ai_model (or env SEO_AI_MODEL)")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce(value: Any, default: Any) -> Any:
    if isinstance(default, bool):
        return value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    if isinstance(default, list):
        items = value if isinstance(value, list) else str(value).split(",")
        return [str(v).strip() for v in items if str(v).strip()]
    return str(value)
