"""Dedicated platform submission adapters with explicit Playwright selectors and visual feedback."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from database.models import Draft, Status
from automation.verification import SubmissionResult, verify_submission_page
from .base import BasePlatformAdapter

if TYPE_CHECKING:
    from automation.browser import VisibleBrowser


class LocalDemoBookmarkingAdapter(BasePlatformAdapter):
    """Adapter for local demonstration and automated testing bookmarking pages."""

    platform_name = "Local Demo Bookmarking"
    platform_domain = "demo-bookmarking.local"

    async def check_auth(self, browser: VisibleBrowser) -> tuple[bool, str | None]:
        # Demo environment is pre-authorized
        return True, None

    async def navigate_to_form(self, browser: VisibleBrowser) -> bool:
        if not browser.page:
            return False
        # Verify submission form fields exist
        try:
            await browser.page.wait_for_selector("form#bookmark-form, form.submission-form, form", timeout=5000)
            return True
        except Exception:
            return False

    async def fill_form(self, browser: VisibleBrowser, draft: Draft) -> tuple[bool, str | None]:
        page = browser.page
        if not page:
            return False, "Page is unavailable"

        try:
            # 1. Fill Target URL
            url_loc = page.locator("input[name='url'], input[type='url'], #url-input").first
            if await url_loc.count() > 0:
                await browser.highlight_and_fill(url_loc, draft.target_url, "target URL")

            # 2. Fill Title
            title_loc = page.locator("input[name='title'], #title-input").first
            if await title_loc.count() > 0:
                await browser.highlight_and_fill(title_loc, draft.title, "title")

            # 3. Fill Description
            desc_loc = page.locator("textarea[name='description'], textarea[name='desc'], #desc-input").first
            if await desc_loc.count() > 0:
                await browser.highlight_and_fill(desc_loc, draft.description, "description")

            # 4. Fill Tags
            tags_loc = page.locator("input[name='tags'], #tags-input").first
            if await tags_loc.count() > 0:
                await browser.highlight_and_fill(tags_loc, draft.tags, "tags")

            # Validate populated values
            if await title_loc.count() > 0:
                val = await title_loc.input_value()
                if draft.title not in val:
                    return False, "Title field validation failed"

            return True, None
        except Exception as exc:
            return False, f"Failed while filling local demo form: {exc}"

    async def submit(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False
        submit_btn = page.locator("button[type='submit'], input[type='submit'], #submit-btn").first
        if await submit_btn.count() > 0:
            await browser.highlight_and_click(submit_btn, "Submit Bookmark")
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            return True
        return False

    async def verify(self, browser: VisibleBrowser, original_url: str, target_url: str) -> SubmissionResult:
        if not browser.page:
            return SubmissionResult(success=False, status=Status.FAILED, error_message="No page open")
        return await verify_submission_page(browser.page, original_url, target_url)


class HackerNewsAdapter(BasePlatformAdapter):
    """Adapter for news.ycombinator.com link and Show HN submissions."""

    platform_name = "Hacker News"
    platform_domain = "news.ycombinator.com"

    async def check_auth(self, browser: VisibleBrowser) -> tuple[bool, str | None]:
        page = browser.page
        if not page:
            return False, "No page open"
        # HN displays user profile link if logged in, or 'login' link if not
        login_link = page.locator("a:text-matches('^login$', 'i')")
        if await login_link.count() > 0:
            return False, "Hacker News session is not logged in. Please log in manually in the visible browser."
        return True, None

    async def navigate_to_form(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False
        try:
            await browser.goto("https://news.ycombinator.com/submit")
            await page.wait_for_selector("form[action='r']", timeout=8000)
            return True
        except Exception:
            return False

    async def fill_form(self, browser: VisibleBrowser, draft: Draft) -> tuple[bool, str | None]:
        page = browser.page
        if not page:
            return False, "No page"
        try:
            title_input = page.locator("input[name='title']").first
            url_input = page.locator("input[name='url']").first

            if await title_input.count() == 0 or await url_input.count() == 0:
                return False, "Hacker News submission input fields not found"

            await browser.highlight_and_fill(title_input, draft.title, "title")
            await browser.highlight_and_fill(url_input, draft.target_url, "target URL")
            return True, None
        except Exception as exc:
            return False, str(exc)

    async def submit(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False
        submit_btn = page.locator("input[type='submit']").first
        if await submit_btn.count() > 0:
            await browser.highlight_and_click(submit_btn, "Submit to Hacker News")
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            return True
        return False

    async def verify(self, browser: VisibleBrowser, original_url: str, target_url: str) -> SubmissionResult:
        if not browser.page:
            return SubmissionResult(success=False, status=Status.FAILED, error_message="No page")
        return await verify_submission_page(browser.page, original_url, target_url)


class DevToAdapter(BasePlatformAdapter):
    """Adapter for Dev.to technical articles and link posts."""

    platform_name = "Dev.to"
    platform_domain = "dev.to"

    async def check_auth(self, browser: VisibleBrowser) -> tuple[bool, str | None]:
        page = browser.page
        if not page:
            return False, "No page"
        enter_link = page.locator("a[href='/enter']")
        if await enter_link.count() > 0:
            return False, "Dev.to account is not signed in. Please log in in the visible browser window."
        return True, None

    async def navigate_to_form(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False
        try:
            await browser.goto("https://dev.to/new")
            await page.wait_for_selector("#article-form-title, textarea[placeholder*='Title']", timeout=10000)
            return True
        except Exception:
            return False

    async def fill_form(self, browser: VisibleBrowser, draft: Draft) -> tuple[bool, str | None]:
        page = browser.page
        if not page:
            return False, "No page"
        try:
            title_loc = page.locator("#article-form-title, textarea[placeholder*='Title']").first
            body_loc = page.locator("#article_body_markdown, textarea[placeholder*='Write your post']").first

            if await title_loc.count() == 0:
                return False, "Dev.to title input not found"

            await browser.highlight_and_fill(title_loc, draft.title, "title")
            if await body_loc.count() > 0:
                await browser.highlight_and_fill(body_loc, f"{draft.description}\n\nCanonical / Reference: {draft.target_url}", "article body")
            return True, None
        except Exception as exc:
            return False, str(exc)

    async def submit(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False
        publish_btn = page.locator("button:has-text('Publish')").first
        if await publish_btn.count() > 0:
            await browser.highlight_and_click(publish_btn, "Publish Article")
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            return True
        return False

    async def verify(self, browser: VisibleBrowser, original_url: str, target_url: str) -> SubmissionResult:
        if not browser.page:
            return SubmissionResult(success=False, status=Status.FAILED, error_message="No page")
        return await verify_submission_page(browser.page, original_url, target_url)


class RedditAdapter(BasePlatformAdapter):
    """Adapter for Reddit link submission."""

    platform_name = "Reddit"
    platform_domain = "reddit.com"

    async def check_auth(self, browser: VisibleBrowser) -> tuple[bool, str | None]:
        page = browser.page
        if not page:
            return False, "No page"
        login_btn = page.locator("a[href*='/login'], button:has-text('Log In')")
        if await login_btn.count() > 0:
            return False, "Reddit session requires authentication. Please log in manually in visible browser."
        return True, None

    async def navigate_to_form(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False
        try:
            await browser.goto("https://www.reddit.com/submit")
            await page.wait_for_selector("textarea[placeholder*='Title'], input[placeholder*='Title']", timeout=10000)
            return True
        except Exception:
            return False

    async def fill_form(self, browser: VisibleBrowser, draft: Draft) -> tuple[bool, str | None]:
        page = browser.page
        if not page:
            return False, "No page"
        try:
            # Switch to Link tab if present
            link_tab = page.locator("button:has-text('Link')").first
            if await link_tab.count() > 0:
                await browser.highlight_and_click(link_tab, "Link Tab")

            title_loc = page.locator("textarea[placeholder*='Title'], input[placeholder*='Title']").first
            url_loc = page.locator("textarea[placeholder*='Url'], input[placeholder*='Url']").first

            if await title_loc.count() == 0:
                return False, "Reddit title input field missing"

            await browser.highlight_and_fill(title_loc, draft.title, "title")
            if await url_loc.count() > 0:
                await browser.highlight_and_fill(url_loc, draft.target_url, "target URL")

            return True, None
        except Exception as exc:
            return False, str(exc)

    async def submit(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False
        post_btn = page.locator("button:has-text('Post')").first
        if await post_btn.count() > 0:
            await browser.highlight_and_click(post_btn, "Post to Reddit")
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            return True
        return False

    async def verify(self, browser: VisibleBrowser, original_url: str, target_url: str) -> SubmissionResult:
        if not browser.page:
            return SubmissionResult(success=False, status=Status.FAILED, error_message="No page")
        return await verify_submission_page(browser.page, original_url, target_url)


class GenericBookmarkingAdapter(BasePlatformAdapter):
    """Fallback adapter for standard social bookmarking platforms with strict selector checks."""

    platform_name = "Generic Bookmarking"
    platform_domain = "generic"

    async def check_auth(self, browser: VisibleBrowser) -> tuple[bool, str | None]:
        intervention = await browser.detect_manual_intervention()
        if intervention:
            return False, intervention
        return True, None

    async def navigate_to_form(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False
        from automation.form_detector import IntelligentFormDetector
        detector = IntelligentFormDetector()
        report = await detector.detect_form(page)
        if report.is_usable:
            return True
        form = page.locator("form")
        return await form.count() > 0

    async def fill_form(self, browser: VisibleBrowser, draft: Draft) -> tuple[bool, str | None]:
        page = browser.page
        if not page:
            return False, "No page"

        try:
            from automation.form_detector import IntelligentFormDetector
            detector = IntelligentFormDetector()
            report = await detector.detect_form(page)
            if report.is_usable:
                return await detector.fill_form_automatically(browser, draft, report, human_like=True)

            # Fallback to standard selector checks
            url_loc = page.locator("input[name*='url'], input[type='url'], input[id*='url']").first
            if await url_loc.count() > 0:
                await browser.highlight_and_fill(url_loc, draft.target_url, "target URL")

            title_loc = page.locator("input[name*='title'], input[id*='title']").first
            if await title_loc.count() > 0:
                await browser.highlight_and_fill(title_loc, draft.title, "title")

            desc_loc = page.locator("textarea[name*='desc'], textarea[id*='desc'], textarea").first
            if await desc_loc.count() > 0:
                await browser.highlight_and_fill(desc_loc, draft.description, "description")

            tags_loc = page.locator("input[name*='tag'], input[id*='tag']").first
            if await tags_loc.count() > 0:
                await browser.highlight_and_fill(tags_loc, draft.tags, "tags")

            return True, None
        except Exception as exc:
            return False, str(exc)

    async def submit(self, browser: VisibleBrowser) -> bool:
        page = browser.page
        if not page:
            return False

        from automation.form_detector import IntelligentFormDetector
        detector = IntelligentFormDetector()
        report = await detector.detect_form(page)
        if report.submit_button:
            await browser.highlight_and_click(report.submit_button.locator, "Submit", human_like=True)
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            return True

        btn = page.locator("button[type='submit'], input[type='submit']").first
        if await btn.count() > 0:
            await browser.highlight_and_click(btn, "Submit")
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            return True
        return False

    async def verify(self, browser: VisibleBrowser, original_url: str, target_url: str) -> SubmissionResult:
        if not browser.page:
            return SubmissionResult(success=False, status=Status.FAILED, error_message="No page")
        return await verify_submission_page(browser.page, original_url, target_url)


# Adapter registry
ADAPTERS: dict[str, BasePlatformAdapter] = {
    "demo-bookmarking.local": LocalDemoBookmarkingAdapter(),
    "127.0.0.1": LocalDemoBookmarkingAdapter(),
    "localhost": LocalDemoBookmarkingAdapter(),
    "techbookmarks.org": LocalDemoBookmarkingAdapter(),
    "rfidpulse.net": LocalDemoBookmarkingAdapter(),
    "devwire.io": LocalDemoBookmarkingAdapter(),
    "enterprisebiznews.com": LocalDemoBookmarkingAdapter(),
    "socialpinseo.org": LocalDemoBookmarkingAdapter(),
    "smartlogisticsreview.com": LocalDemoBookmarkingAdapter(),
    "iotnetworkdigest.net": LocalDemoBookmarkingAdapter(),
    "techspotlightdaily.org": LocalDemoBookmarkingAdapter(),
    "news.ycombinator.com": HackerNewsAdapter(),
    "dev.to": DevToAdapter(),
    "reddit.com": RedditAdapter(),
}


def get_adapter(domain: str) -> BasePlatformAdapter | None:
    domain_clean = domain.strip().lower().removeprefix("www.")
    if domain_clean in ADAPTERS:
        return ADAPTERS[domain_clean]
    # For domains matching test/demo hostnames
    if "127.0.0.1" in domain_clean or "localhost" in domain_clean or "demo" in domain_clean:
        return LocalDemoBookmarkingAdapter()
    return GenericBookmarkingAdapter()

