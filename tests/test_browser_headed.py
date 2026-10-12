import os
import pytest
from unittest.mock import patch, MagicMock
from config import Settings
from automation.browser import VisibleBrowser


def test_headed_mode_default_configuration():
    """Confirms that the default configuration launches Chromium in headed mode with slow_mo."""
    settings = Settings()
    assert settings.headless is False, "Default mode must be headed (headless=False)"
    assert settings.slow_mo == 300, "Default slow_mo should be 300ms for visible inspection"


def test_display_environment_check_when_headed():
    """Confirms that running headed in an environment without a display raises an informative error."""
    settings = Settings(headless=False)
    browser = VisibleBrowser(settings)

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError) as exc_info:
            browser._verify_display_environment()
        assert "No graphical desktop display detected" in str(exc_info.value)
        assert "--headless" in str(exc_info.value)


def test_display_environment_check_passes_with_display():
    """Confirms that display check passes when DISPLAY is present."""
    settings = Settings(headless=False)
    browser = VisibleBrowser(settings)

    with patch.dict(os.environ, {"DISPLAY": ":0"}):
        browser._verify_display_environment()  # Should not raise


def test_display_check_skipped_when_headless_explicit():
    """Confirms that headless mode runs even without DISPLAY."""
    settings = Settings(headless=True)
    browser = VisibleBrowser(settings)

    with patch.dict(os.environ, {}, clear=True):
        browser._verify_display_environment()  # Should not raise
