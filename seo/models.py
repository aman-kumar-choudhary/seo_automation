"""Data models for Technical SEO Crawling, Audits, Directives, and Search Console Analytics."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class RedirectHop:
    url: str
    status_code: int


@dataclass
class ImageAudit:
    src: str
    alt: str
    has_alt: bool


@dataclass
class PageAuditResult:
    url: str
    status_code: int = 200
    ttfb_ms: float = 0.0
    redirect_chain: list[RedirectHop] = field(default_factory=list)
    title: str = ""
    title_length: int = 0
    title_issues: list[str] = field(default_factory=list)
    meta_description: str = ""
    meta_description_length: int = 0
    meta_description_issues: list[str] = field(default_factory=list)
    h1_tags: list[str] = field(default_factory=list)
    h1_issues: list[str] = field(default_factory=list)
    canonical_url: str = ""
    canonical_issues: list[str] = field(default_factory=list)
    robots_meta: str = ""
    robots_meta_issues: list[str] = field(default_factory=list)
    images: list[ImageAudit] = field(default_factory=list)
    missing_alt_count: int = 0
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    structured_data_types: list[str] = field(default_factory=list)
    structured_data_issues: list[str] = field(default_factory=list)
    page_score: int = 100
    crawled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchConsoleMetrics:
    configured: bool = False
    total_clicks: int = 0
    total_impressions: int = 0
    average_ctr: float = 0.0
    average_position: float = 0.0
    top_queries: list[dict[str, Any]] = field(default_factory=list)
    top_pages: list[dict[str, Any]] = field(default_factory=list)
    details: str = "Search Console API access not configured; using offline mode."


@dataclass
class SiteAuditReport:
    target_url: str
    target_domain: str
    total_pages_crawled: int = 0
    overall_seo_score: int = 0
    grade: str = "F"
    broken_internal_links: list[dict[str, Any]] = field(default_factory=list)
    redirect_chains: list[dict[str, Any]] = field(default_factory=list)
    missing_titles_count: int = 0
    duplicate_titles_count: int = 0
    missing_meta_descriptions_count: int = 0
    missing_h1_count: int = 0
    multiple_h1_count: int = 0
    images_without_alt_count: int = 0
    robots_txt_status: str = "VALID"
    robots_txt_issues: list[str] = field(default_factory=list)
    sitemap_status: str = "VALID"
    sitemap_issues: list[str] = field(default_factory=list)
    structured_data_present: bool = False
    structured_data_types: list[str] = field(default_factory=list)
    search_console: SearchConsoleMetrics = field(default_factory=SearchConsoleMetrics)
    pages: list[PageAuditResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)
