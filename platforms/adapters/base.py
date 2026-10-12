from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from database.models import Draft
from automation.verification import SubmissionResult

if TYPE_CHECKING:
    from automation.browser import VisibleBrowser


class BasePlatformAdapter(ABC):
    """Abstract base adapter for platform-specific Playwright submission workflows."""

    platform_name: str = "Base"
    platform_domain: str = ""

    @abstractmethod
    async def check_auth(self, browser: VisibleBrowser) -> tuple[bool, str | None]:
        """Checks whether the browser session is authenticated on the platform.
        
        Returns (is_logged_in, intervention_message_if_not).
        """
        pass

    @abstractmethod
    async def navigate_to_form(self, browser: VisibleBrowser) -> bool:
        """Navigates to the platform's bookmarking/submission form and confirms elements."""
        pass

    @abstractmethod
    async def fill_form(self, browser: VisibleBrowser, draft: Draft) -> tuple[bool, str | None]:
        """Locates and populates title, description, target URL, and tags with visual DOM highlighting."""
        pass

    @abstractmethod
    async def submit(self, browser: VisibleBrowser) -> bool:
        """Triggers the final publish button in the browser (called ONLY after approval & NOT in dry run)."""
        pass

    @abstractmethod
    async def verify(self, browser: VisibleBrowser, original_url: str, target_url: str) -> SubmissionResult:
        """Verifies submission confirmation, redirects, or platform error states."""
        pass
