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
