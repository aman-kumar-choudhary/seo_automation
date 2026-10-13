"""Account credentials and persistent session manager for social bookmarking platforms.

Stores and restores Playwright browser storage state (cookies, localStorage, session tokens)
so accounts stay signed in across browser launches without requiring repetitive manual login.
Also provides automated login form population from credentials.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING
from playwright.async_api import BrowserContext, Page, Locator

if TYPE_CHECKING:
    from config import Settings
    from database.repository import Repository
    from automation.browser import VisibleBrowser

logger = logging.getLogger(__name__)


class AccountManager:
    """Manages credentials and persistent session states across candidate domains."""

    def __init__(self, settings: Settings, repo: Repository | None = None):
        self.settings = settings
        self.repo = repo
        self.session_dir = Path(settings.session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.credentials_file = Path(settings.credentials_path)
        self._memory_credentials: dict[str, dict[str, str]] = {}
        self._load_credentials_file()

    def _load_credentials_file(self) -> None:
        """Loads optional credentials JSON file if present."""
        if self.credentials_file.exists():
            try:
                data = json.loads(self.credentials_file.read_text(encoding="utf-8"))
                for domain, creds in data.items():
                    clean_d = domain.strip().lower().removeprefix("www.")
                    self._memory_credentials[clean_d] = creds
            except Exception as exc:
                logger.warning("Could not read credentials file %s: %s", self.credentials_file, exc)

    def get_credentials(self, domain: str) -> dict[str, str] | None:
        """Retrieves stored username and password for a domain from memory, file, or SQLite."""
        clean_d = domain.strip().lower().removeprefix("www.")
        if clean_d in self._memory_credentials:
            return self._memory_credentials[clean_d]

        if self.repo:
            row = self.repo.get_account(clean_d)
            if row:
                return {"username": row["username"], "password": row["password"]}

        return None

    def store_credentials(self, domain: str, username: str, password: str) -> None:
        """Stores credentials in memory, SQLite repository, and optionally credentials file."""
        clean_d = domain.strip().lower().removeprefix("www.")
        self._memory_credentials[clean_d] = {"username": username, "password": password}
        if self.repo:
            self.repo.upsert_account(clean_d, username, password)

    def get_session_path(self, domain: str) -> Path:
        """Gets deterministic session storage file path for a domain."""
        clean_d = domain.strip().lower().removeprefix("www.").replace(":", "_")
        return self.session_dir / f"{clean_d}_session.json"

    def has_saved_session(self, domain: str) -> bool:
        """Checks if a valid saved session state exists for a domain."""
        path = self.get_session_path(domain)
        return path.exists() and path.stat().st_size > 30

    async def save_session_state(self, context: BrowserContext, domain: str) -> str:
        """Dumps authenticated cookies and storage state to disk."""
        path = self.get_session_path(domain)
        try:
            await context.storage_state(path=str(path))
            if self.repo:
                self.repo.update_account_session(domain, str(path))
            logger.info("Saved persistent session state for %s at %s", domain, path)
            return str(path)
        except Exception as exc:
            logger.warning("Failed to save storage state for %s: %s", domain, exc)
            return ""

    async def auto_login(self, browser: VisibleBrowser, domain: str) -> tuple[bool, str | None]:
        """Automatically detects login form fields, populates credentials, and submits."""
        page = browser.page
        if not page:
            return False, "Browser page not available"

        creds = self.get_credentials(domain)
        if not creds:
            return False, f"No credentials configured for domain '{domain}'"

        username = creds.get("username") or creds.get("email") or ""
        password = creds.get("password") or ""

        if not username or not password:
            return False, "Incomplete credentials (username or password missing)"

        try:
            # 1. Locate password input
            pw_loc = page.locator("input[type='password']")
            if await pw_loc.count() == 0:
                return False, "Password input field not detected on current page"
            pw_input = pw_loc.first

            # 2. Locate username or email input
            user_loc = page.locator(
                "input[name*='user' i], input[name*='email' i], input[name*='login' i], "
                "input[id*='user' i], input[id*='email' i], input[type='email'], input[type='text']"
            )
            if await user_loc.count() == 0:
                return False, "Username/email input field not detected"
            user_input = user_loc.first

            # 3. Highlight and fill username
            await browser.highlight_and_fill(user_input, username, "username/email", human_like=True)

            # 4. Highlight and fill password
            await browser.highlight_and_fill(pw_input, password, "password", human_like=False)

            # 5. Locate and click submit / sign-in button
            submit_loc = page.locator(
                "button[type='submit'], input[type='submit'], "
                "button:has-text('Sign In'), button:has-text('Log In'), button:has-text('Login')"
            )
            if await submit_loc.count() > 0:
                submit_btn = submit_loc.first
                await browser.highlight_and_click(submit_btn, "Login / Sign In")
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    pass

            # 6. Verify if still on login form or successfully transitioned
            still_pw = await page.locator("input[type='password']").count()
            if still_pw == 0 or "login" not in (page.url or "").lower():
                # Save session immediately!
                if browser.context:
                    await self.save_session_state(browser.context, domain)
                return True, None

            return False, "Login submitted but password field is still present"

        except Exception as exc:
            return False, f"Auto-login failed: {exc}"
