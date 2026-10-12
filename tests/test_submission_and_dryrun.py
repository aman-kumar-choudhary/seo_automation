import pytest
from unittest.mock import AsyncMock
from playwright.async_api import async_playwright
from config import Settings
from database.models import Status
from database.repository import Repository
from automation.verification import verify_submission_page
from automation.screenshots import ScreenshotManager
from automation.submission import SubmissionOrchestrator
from automation.browser import VisibleBrowser
from dashboard.app import EventHub
from automation.controller import WorkflowController, Monitor


@pytest.mark.asyncio
async def test_verification_detects_success_and_error():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        # Success page
        await page.set_content("""
            <html><body>
                <h1>Thank you for your submission</h1>
                <p>Your bookmark has been published successfully.</p>
            </body></html>
        """)
        res_success = await verify_submission_page(page, "http://example.com/submit", "https://innovions.org/")
        assert res_success.success is True
        assert res_success.status == Status.PUBLISHED

        # Error page
        await page.set_content("""
            <html><body>
                <div class="alert alert-danger">Error: Duplicate URL already exists on this platform.</div>
            </body></html>
        """)
        res_error = await verify_submission_page(page, "http://example.com/submit", "https://innovions.org/")
        assert res_error.success is False
        assert res_error.status == Status.FAILED
        assert "duplicate" in res_error.error_message.lower()

        await browser.close()


@pytest.mark.asyncio
async def test_dry_run_blocks_publishing(tmp_path):
    """Verifies that in dry-run mode, the submit button is NOT clicked and content is NOT published."""
    settings = Settings(database_path=tmp_path / "test.db", dry_run=True, manual_approval=False, headless=True)
    repo = Repository(settings.database_path)
    hub = EventHub()

    form_html_url = (
        "data:text/html;charset=utf-8,"
        "<html><body>"
        "<form id='bookmark-form'>"
        "<input name='url' type='url' />"
        "<input name='title' type='text' />"
        "<textarea name='description'></textarea>"
        "<input name='tags' type='text' />"
        "<button type='submit' id='submit-btn'>Submit Bookmark</button>"
        "</form>"
        "</body></html>"
    )

    pid = repo.upsert_platform({
        "name": "Demo Bookmark",
        "domain": "demo-bookmarking.local",
        "submission_url": form_html_url,
    })
    repo.save_draft(pid, "RFID Tracking Architecture", "Explore industrial RFID hardware at https://innovions.org/", "https://innovions.org/", "RFID", True)
    repo.approve_draft(pid, True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        visible_browser = VisibleBrowser(settings)
        visible_browser.page = page
        visible_browser.context = context
        visible_browser.browser = browser
        visible_browser.screenshot_mgr = ScreenshotManager(tmp_path / "screenshots")

        # Spy on highlight_and_click to ensure it is never called in dry run
        click_mock = AsyncMock()
        visible_browser.highlight_and_click = click_mock

        controller = WorkflowController(settings, repo, hub, visible_browser)
        monitor = Monitor(hub)
        orchestrator = SubmissionOrchestrator(settings, repo, visible_browser, monitor, controller)

        platform_row = dict(repo.get_platform(pid))
        result = await orchestrator.execute(platform_row)

        # In dry run, result must indicate publication was withheld
        assert result.success is True
        assert result.status == Status.AWAITING_APPROVAL
        # Submit button was NOT clicked
        click_mock.assert_not_called()

        await browser.close()


def test_screenshot_manager_file_generation(tmp_path):
    mgr = ScreenshotManager(tmp_path / "shots")
    path = mgr._generate_path("test", "Reddit")
    assert "test_Reddit" in str(path)
    assert path.suffix == ".png"
