from __future__ import annotations

import re
from dataclasses import dataclass
from playwright.async_api import Page
from database.models import Status


@dataclass
class SubmissionResult:
    success: bool
    status: Status
    published_url: str | None = None
    error_message: str | None = None
    screenshot_path: str | None = None


SUCCESS_PATTERNS = [
    re.compile(r"submission\s+(?:successful|received|complete|approved)", re.IGNORECASE),
    re.compile(r"your\s+(?:link|bookmark|story|post)\s+(?:has\s+been|was)\s+(?:submitted|added|published|created)", re.IGNORECASE),
    re.compile(r"bookmark\s+added", re.IGNORECASE),
    re.compile(r"successfully\s+shared", re.IGNORECASE),
    re.compile(r"thank\s+you\s+for\s+(?:your\s+submission|sharing)", re.IGNORECASE),
    re.compile(r"view\s+your\s+(?:post|submission|story)", re.IGNORECASE),
    re.compile(r"permalink", re.IGNORECASE),
]

ERROR_PATTERNS = [
    re.compile(r"already\s+been\s+submitted", re.IGNORECASE),
    re.compile(r"duplicate\s+(?:url|link|submission)", re.IGNORECASE),
    re.compile(r"spam\s+(?:detected|filter|blocked)", re.IGNORECASE),
    re.compile(r"rate\s+limit(?:ed|\s+exceeded)", re.IGNORECASE),
    re.compile(r"captcha\s+(?:failed|invalid|required)", re.IGNORECASE),
    re.compile(r"please\s+(?:log\s+in|sign\s+in)\s+to\s+submit", re.IGNORECASE),
    re.compile(r"access\s+denied|forbidden|unauthorized", re.IGNORECASE),
    re.compile(r"submission\s+failed|error\s+submitting", re.IGNORECASE),
]


async def verify_submission_page(
    page: Page,
    original_url: str,
    target_url: str,
) -> SubmissionResult:
    """Verifies whether a platform submission actually succeeded or failed on page.
    
    Never marks a submission as published merely because the submit button was clicked.
    """
    current_url = page.url

    # Check for error banners / alert texts first
    try:
        body_text = await page.inner_text("body", timeout=5000)
    except Exception as exc:
        return SubmissionResult(
            success=False,
            status=Status.FAILED,
            error_message=f"Could not read page verification text: {exc}",
        )

    for pattern in ERROR_PATTERNS:
        match = pattern.search(body_text)
        if match:
            return SubmissionResult(
                success=False,
                status=Status.FAILED,
                error_message=f"Platform returned error: '{match.group(0)}'",
            )

    # Check URL redirection from submission endpoint to item/post endpoint
    url_changed = (
        current_url != original_url
        and not current_url.endswith("/submit")
        and not current_url.endswith("/new")
        and not current_url.endswith("/add")
    )

    for pattern in SUCCESS_PATTERNS:
        if pattern.search(body_text):
            # Success confirmation detected in text
            published_url = current_url if url_changed else None
            return SubmissionResult(
                success=True,
                status=Status.PUBLISHED,
                published_url=published_url,
            )

    if url_changed and "login" not in current_url.lower() and "error" not in current_url.lower():
        # URL redirected to a new permanent location
        return SubmissionResult(
            success=True,
            status=Status.PUBLISHED,
            published_url=current_url,
        )

    return SubmissionResult(
        success=False,
        status=Status.FAILED,
        error_message="Submission could not be confirmed: No confirmation banner or verified redirect URL was observed.",
    )
