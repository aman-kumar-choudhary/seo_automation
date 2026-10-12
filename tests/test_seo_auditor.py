import pytest
from unittest.mock import AsyncMock, MagicMock
from automation.seo_auditor import TechnicalSEOAuditor, BacklinkAuditResult


@pytest.mark.asyncio
async def test_seo_auditor_dofollow_with_keyword():
    auditor = TechnicalSEOAuditor(primary_keyword="RFID")
    
    html = """
    <html>
      <head>
        <title>Tech Showcase</title>
        <meta name="robots" content="index, follow">
      </head>
      <body>
        <h1>Recommended IT Tools</h1>
        <p>Explore <a href="https://innovions.org/">Innovions RFID Systems</a> for automated inventory.</p>
      </body>
    </html>
    """

    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value=html)
    mock_page.url = "https://example-tech.com/bookmark/101"

    result = await auditor.audit_url("https://example-tech.com/bookmark/101", "https://innovions.org/", page=mock_page)

    assert result.link_found is True
    assert result.is_dofollow is True
    assert result.has_primary_keyword is True
    assert "RFID" in result.anchor_text
    assert result.quality_score >= 90


@pytest.mark.asyncio
async def test_seo_auditor_nofollow_penalty():
    auditor = TechnicalSEOAuditor(primary_keyword="RFID")
    
    html = """
    <html>
      <head><meta name="robots" content="index, follow"></head>
      <body>
        <a href="https://innovions.org/" rel="nofollow ugc">Innovions</a>
      </body>
    </html>
    """

    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value=html)
    mock_page.url = "https://forum.example.com/post/2"

    result = await auditor.audit_url("https://forum.example.com/post/2", "https://innovions.org/", page=mock_page)

    assert result.link_found is True
    assert result.is_dofollow is False
    assert "nofollow" in result.rel_attribute
    assert "ugc" in result.rel_attribute
    assert result.quality_score < 80


@pytest.mark.asyncio
async def test_seo_auditor_noindex_detection():
    auditor = TechnicalSEOAuditor(primary_keyword="RFID")
    
    html = """
    <html>
      <head><meta name="robots" content="noindex, nofollow"></head>
      <body>
        <a href="https://innovions.org/">RFID Solutions</a>
      </body>
    </html>
    """

    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value=html)
    mock_page.url = "https://private.example.com/page"

    result = await auditor.audit_url("https://private.example.com/page", "https://innovions.org/", page=mock_page)

    assert result.link_found is True
    assert result.quality_score == 0
    assert any("noindex" in issue.lower() for issue in result.issues)
