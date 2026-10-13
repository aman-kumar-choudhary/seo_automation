"""Tests for persistent session storage and account credential management."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from config import Settings
from database.repository import Repository
from automation.account_manager import AccountManager


def test_account_manager_credentials_and_persistence(tmp_path):
    db_file = tmp_path / "test.db"
    repo = Repository(db_file)
    settings = Settings(
        database_path=db_file,
        session_dir=tmp_path / "sessions",
        credentials_path=tmp_path / "credentials.json",
    )

    manager = AccountManager(settings, repo)

    # Store credentials
    manager.store_credentials("reddit.com", "test_user", "secure_pass_123")
    creds = manager.get_credentials("reddit.com")
    assert creds is not None
    assert creds["username"] == "test_user"
    assert creds["password"] == "secure_pass_123"

    # Normalize domain www check
    creds_www = manager.get_credentials("www.reddit.com")
    assert creds_www == creds

    # Session storage path
    session_file = manager.get_session_path("reddit.com")
    assert session_file.name == "reddit.com_session.json"
    assert not manager.has_saved_session("reddit.com")

    # Write dummy session data
    session_file.write_text('{"cookies": [{"name": "auth", "value": "xyz"}]}', encoding="utf-8")
    assert manager.has_saved_session("reddit.com")


@pytest.mark.asyncio
async def test_account_manager_auto_login(tmp_path):
    db_file = tmp_path / "test.db"
    repo = Repository(db_file)
    settings = Settings(database_path=db_file, session_dir=tmp_path / "sessions")
    manager = AccountManager(settings, repo)
    manager.store_credentials("dev.to", "dev_author", "dev_pass_999")

    # Mock visible browser and page
    mock_browser = MagicMock()
    mock_page = MagicMock()
    mock_browser.page = mock_page
    mock_browser.context = AsyncMock()

    mock_pw_input = AsyncMock()
    mock_pw_input.count.return_value = 1

    mock_user_input = AsyncMock()
    mock_user_input.count.return_value = 1

    mock_btn = AsyncMock()
    mock_btn.count.return_value = 1

    # Locator dispatch
    def locator_side_effect(selector):
        loc = AsyncMock()
        loc.first = loc
        if "password" in selector:
            loc.count.return_value = 1
            return loc
        elif "user" in selector or "email" in selector:
            loc.count.return_value = 1
            return loc
        elif "submit" in selector or "Sign In" in selector or "Log In" in selector:
            loc.count.return_value = 1
            return loc
        loc.count.return_value = 0
        return loc

    mock_page.locator.side_effect = locator_side_effect
    mock_page.url = "https://dev.to/dashboard"
    mock_browser.highlight_and_fill = AsyncMock()
    mock_browser.highlight_and_click = AsyncMock()

    success, err = await manager.auto_login(mock_browser, "dev.to")
    assert success is True
    assert err is None
    assert mock_browser.highlight_and_fill.call_count == 2
    assert mock_browser.highlight_and_click.call_count == 1
