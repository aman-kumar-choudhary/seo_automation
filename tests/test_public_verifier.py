"""Tests for independent unauthenticated public post verification."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from automation.public_verifier import PublicPostVerifier


@pytest.mark.asyncio
async def test_public_verifier_local_demo():
    verifier = PublicPostVerifier(target_url="https://innovions.org/")
    res = await verifier.verify_public_url("http://127.0.0.1:8766/post/101")
    assert res.is_publicly_visible is True
    assert res.public_link_verified is True
    assert res.destination_http_code == 200
    assert res.moderation_status == "APPROVED_PUBLIC"


@pytest.mark.asyncio
async def test_public_verifier_detects_login_wall():
    verifier = PublicPostVerifier(target_url="https://innovions.org/")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://example.com/login?redirect=/post/101"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await verifier.verify_public_url("https://example.com/post/101")
        assert res.is_publicly_visible is False
        assert res.moderation_status == "LOGIN_REQUIRED"


@pytest.mark.asyncio
async def test_public_verifier_detects_pending_moderation():
    verifier = PublicPostVerifier(target_url="https://innovions.org/")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://example.com/post/101"
    mock_resp.text = """
    <html><body>
      <h1>Article Title</h1>
      <p class="notice">This post is awaiting moderation before public indexation.</p>
      <a href="https://innovions.org/">Innovions RFID</a>
    </body></html>
    """

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await verifier.verify_public_url("https://example.com/post/101")
        assert "MODERATION_PENDING" in res.moderation_status
        assert res.public_link_verified is True
