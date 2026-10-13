from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class Status(StrEnum):
    DISCOVERED = "DISCOVERED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"
    ELIGIBLE = "ELIGIBLE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    IN_PROGRESS = "IN_PROGRESS"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class PlatformCandidate:
    name: str
    domain: str
    registration_url: str = ""
    submission_url: str = ""
    relevance: str = ""
    terms_url: str = ""
    registration_requirements: str = "Standard account required"
    link_attributes: str = "rel='nofollow' / user-generated content"
    public_visibility: str = "Publicly indexable"
    posting_restrictions: str = "Follow community terms; no spamming"
    available: bool = True


@dataclass
class Draft:
    title: str
    description: str
    target_url: str
    tags: str
    valid: bool = False
    approval_status: str = "PENDING"


@dataclass
class SubmissionRecord:
    platform_id: int
    draft_id: int | None
    target_url: str
    status: Status
    published_url: str | None = None
    error_message: str | None = None
    screenshot_path: str | None = None
    retry_count: int = 0


@dataclass
class AccountCredential:
    domain: str
    username: str
    password: str
    storage_state_path: str | None = None
    last_login_at: str | None = None


@dataclass
class ContentEvaluationResult:
    relevance_score: float
    accuracy_score: float
    readability_score: float
    safety_score: float
    composite_score: float
    grade: str
    auto_approved: bool
    justification: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


@dataclass
class PublicVerificationResult:
    published_url: str
    is_publicly_visible: bool = False
    public_link_verified: bool = False
    destination_http_code: int = 200
    moderation_status: str | None = None
    details: str = ""
    verified_at: str = ""

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


@dataclass
class CampaignAnalyticsResult:
    domain: str
    utm_url: str
    traffic_tier: str = "Medium"
    estimated_monthly_impressions: int = 0
    equity_value_score: float = 0.0
    created_at: str = ""

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)
