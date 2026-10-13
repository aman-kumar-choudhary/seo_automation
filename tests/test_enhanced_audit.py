"""Tests for enhanced technical SEO backlink auditor (robots.txt, canonical match, grade)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from automation.seo_auditor import TechnicalSEOAuditor


@pytest.mark.asyncio
async def test_seo_auditor_canonical_mismatch():
    auditor = TechnicalSEOAuditor(primary_keyword="RFID")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.text = """
    <html><head>
      <link rel="canonical" href="https://otherdomain.com/canonical-source" />
    </head><body>
      <a href="https://innovions.org/" rel="dofollow">RFID Innovions</a>
    </body></html>
    """

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await auditor.audit_url("https://platform.com/post/1", "https://innovions.org/")
        assert res.canonical_matched is False
        assert any("Canonical URL points to different target" in issue for issue in res.issues)
        assert res.indexability_grade in ("A", "B", "C")


@pytest.mark.asyncio
async def test_seo_auditor_grade_calculation():
    auditor = TechnicalSEOAuditor(primary_keyword="RFID")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.text = """
    <html><head>
      <meta name="robots" content="index, follow" />
      <link rel="canonical" href="https://platform.com/post/100" />
    </head><body>
      <a href="https://innovions.org/" rel="dofollow">Innovions RFID Solutions</a>
    </body></html>
    """

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await auditor.audit_url("https://platform.com/post/100", "https://innovions.org/")
        assert res.link_found is True
        assert res.is_dofollow is True
        assert res.has_primary_keyword is True
        assert res.quality_score >= 90
        assert res.indexability_grade == "A+"
