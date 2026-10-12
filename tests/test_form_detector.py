import pytest
from unittest.mock import AsyncMock, MagicMock
from automation.form_detector import IntelligentFormDetector, FormDetectionReport, FormFieldMatch
from database.models import Draft


@pytest.mark.asyncio
async def test_form_detector_identifies_fields():
    mock_page = MagicMock()

    # Create mock locators that return visible for URL, Title, Desc, and Submit
    url_loc = AsyncMock()
    url_loc.count = AsyncMock(return_value=1)
    url_loc.is_visible = AsyncMock(return_value=True)

    title_loc = AsyncMock()
    title_loc.count = AsyncMock(return_value=1)
    title_loc.is_visible = AsyncMock(return_value=True)

    desc_loc = AsyncMock()
    desc_loc.count = AsyncMock(return_value=1)
    desc_loc.is_visible = AsyncMock(return_value=True)
    desc_loc.evaluate = AsyncMock(return_value="textarea")
    desc_loc.get_attribute = AsyncMock(return_value=None)

    btn_loc = AsyncMock()
    btn_loc.count = AsyncMock(return_value=1)
    btn_loc.is_visible = AsyncMock(return_value=True)

    empty_loc = AsyncMock()
    empty_loc.count = AsyncMock(return_value=0)
    empty_loc.is_visible = AsyncMock(return_value=False)

    def mock_locator(sel):
        if "url" in sel:
            m = MagicMock()
            m.first = url_loc
            return m
        elif "title" in sel:
            m = MagicMock()
            m.first = title_loc
            return m
        elif "desc" in sel:
            m = MagicMock()
            m.first = desc_loc
            return m
        elif "Submit" in sel:
            m = MagicMock()
            m.first = btn_loc
            return m
        m = MagicMock()
        m.first = empty_loc
        m.count = AsyncMock(return_value=0)
        return m

    mock_page.locator.side_effect = mock_locator

    detector = IntelligentFormDetector()
    report = await detector.detect_form(mock_page)

    assert report.is_usable
    assert report.url_field is not None
    assert report.title_field is not None
    assert report.description_field is not None
    assert report.detected_fields_count >= 3
    assert report.confidence_score >= 0.7


@pytest.mark.asyncio
async def test_form_detector_auto_fill():
    mock_browser = MagicMock()
    mock_browser.page = MagicMock()
    mock_browser.highlight_and_fill = AsyncMock()
    mock_browser.highlight = AsyncMock()
    mock_browser.unhighlight = AsyncMock()

    url_match = FormFieldMatch(field_type="url", selector="#url", locator=AsyncMock())
    title_match = FormFieldMatch(field_type="title", selector="#title", locator=AsyncMock())
    desc_match = FormFieldMatch(field_type="description", selector="#desc", locator=AsyncMock(), element_tag="textarea")

    report = FormDetectionReport(
        url_field=url_match,
        title_field=title_match,
        description_field=desc_match,
    )

    draft = Draft(
        title="RFID Solutions - Innovions",
        description="Discover RFID automated tracking at https://innovions.org/",
        target_url="https://innovions.org/",
        tags="RFID, tracking",
    )

    detector = IntelligentFormDetector()
    success, err = await detector.fill_form_automatically(mock_browser, draft, report, human_like=False)

    assert success is True
    assert err is None
    assert mock_browser.highlight_and_fill.await_count >= 2
