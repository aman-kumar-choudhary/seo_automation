"""Tests for safe CAPTCHA detection and authorized human pause resolution."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from config import Settings
from automation.captcha_solver import CaptchaSolver, CaptchaInfo, CaptchaSolveResult


@pytest.mark.asyncio
async def test_captcha_detection_recaptcha():
    settings = Settings(captcha_detection_enabled=True)
    solver = CaptchaSolver(settings)

    mock_page = MagicMock()

    def locator_side_effect(selector):
        loc = AsyncMock()
        loc.first = loc
        if "recaptcha" in selector:
            loc.count.return_value = 1
            loc.get_attribute.return_value = "https://www.google.com/recaptcha/api2/anchor?k=6Ld_sample_key_123"
            return loc
        loc.count.return_value = 0
        return loc

    mock_page.locator.side_effect = locator_side_effect

    info = await solver.detect_captcha(mock_page)
    assert info is not None
    assert info.captcha_type == "recaptcha_v2"
    assert info.sitekey == "6Ld_sample_key_123"


@pytest.mark.asyncio
async def test_captcha_solver_pauses_for_human_resolution():
    settings = Settings(captcha_detection_enabled=True, captcha_pause_timeout_seconds=0.1)
    solver = CaptchaSolver(settings)

    mock_browser = MagicMock()
    mock_browser.monitor = MagicMock()
    mock_browser.monitor.log = AsyncMock()
    mock_browser.monitor.set_intervention = AsyncMock()
    mock_browser.controller = None

    mock_page = MagicMock()
    mock_page.evaluate = AsyncMock(return_value=False)
    loc = AsyncMock()
    loc.count.return_value = 1
    mock_page.locator.return_value = loc
    mock_browser.page = mock_page

    info = CaptchaInfo(captcha_type="recaptcha_v2", sitekey="sample_key")
    result = await solver._pause_for_human_resolution(mock_browser, info)

    assert result.solved is False
    assert result.method == "human_resolution"
    assert "timed out" in (result.error_message or "").lower()
    mock_browser.monitor.set_intervention.assert_awaited()
