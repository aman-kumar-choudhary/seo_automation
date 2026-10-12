"""Intelligent Form & Rich-Text Editor Detector for Social Bookmarking Platforms.

Automatically inspects DOM structures, detects inputs, textareas, contenteditable containers,
select dropdowns (matching technology/business categories), and submit buttons.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from playwright.async_api import Page, Locator

if TYPE_CHECKING:
    from automation.browser import VisibleBrowser
    from database.models import Draft

logger = logging.getLogger(__name__)


@dataclass
class FormFieldMatch:
    field_type: str  # 'url', 'title', 'description', 'tags', 'category', 'submit'
    selector: str
    locator: Locator
    confidence: float = 1.0
    element_tag: str = "input"
    is_contenteditable: bool = False


@dataclass
class FormDetectionReport:
    url_field: FormFieldMatch | None = None
    title_field: FormFieldMatch | None = None
    description_field: FormFieldMatch | None = None
    tags_field: FormFieldMatch | None = None
    category_select: FormFieldMatch | None = None
    submit_button: FormFieldMatch | None = None
    confidence_score: float = 0.0
    detected_fields_count: int = 0

    @property
    def is_usable(self) -> bool:
        """A form is considered usable if at least title or url or description is found."""
        return bool(self.title_field or self.url_field or self.description_field)


class IntelligentFormDetector:
    """Scans pages using multi-strategy selector heuristics to identify bookmark submission forms."""

    URL_SELECTORS = [
        "input[type='url']",
        "input[name*='url' i]",
        "input[id*='url' i]",
        "input[placeholder*='url' i]",
        "input[placeholder*='link' i]",
        "input[placeholder*='http' i]",
        "input[name*='link' i]",
        "input[id*='link' i]",
        "input[name*='website' i]",
        "input[id*='website' i]",
        "input[name='target']",
        "#url-input",
    ]

    TITLE_SELECTORS = [
        "input[name*='title' i]",
        "input[id*='title' i]",
        "input[placeholder*='title' i]",
        "input[name*='headline' i]",
        "input[id*='headline' i]",
        "input[name*='subject' i]",
        "input[name*='name' i]:not([name*='user']):not([name*='author'])",
        "#title-input",
    ]

    DESCRIPTION_SELECTORS = [
        "textarea[name*='desc' i]",
        "textarea[id*='desc' i]",
        "textarea[placeholder*='desc' i]",
        "textarea[name*='content' i]",
        "textarea[id*='content' i]",
        "textarea[name*='body' i]",
        "textarea[name*='summary' i]",
        "textarea[name*='text' i]",
        "div[contenteditable='true']",
        "[role='textbox']",
        ".ProseMirror",
        ".ql-editor",
        "#desc-input",
        "textarea",
    ]

    TAGS_SELECTORS = [
        "input[name*='tag' i]",
        "input[id*='tag' i]",
        "input[placeholder*='tag' i]",
        "input[name*='keyword' i]",
        "input[id*='keyword' i]",
        "input[placeholder*='keyword' i]",
        "input[name*='label' i]",
        "#tags-input",
    ]

    SUBMIT_SELECTORS = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit')",
        "button:has-text('Publish')",
        "button:has-text('Post')",
        "button:has-text('Bookmark')",
        "button:has-text('Share')",
        "button:has-text('Save')",
        "#submit-btn",
        ".submit-button",
    ]

    PREFERRED_CATEGORIES = [
        "technology", "tech", "business", "iot", "software",
        "hardware", "internet", "electronics", "computers", "science", "rfid"
    ]

    async def detect_form(self, page: Page) -> FormDetectionReport:
        """Inspects the page DOM and resolves the best matching form elements."""
        report = FormDetectionReport()

        # 1. Detect URL Field
        for sel in self.URL_SELECTORS:
            loc = page.locator(sel).first
            try:
                if await loc.count() > 0 and await loc.is_visible():
                    report.url_field = FormFieldMatch(
                        field_type="url",
                        selector=sel,
                        locator=loc,
                        confidence=0.9 if "url" in sel else 0.75,
                    )
                    break
            except Exception:
                continue

        # 2. Detect Title Field
        for sel in self.TITLE_SELECTORS:
            loc = page.locator(sel).first
            try:
                if await loc.count() > 0 and await loc.is_visible():
                    report.title_field = FormFieldMatch(
                        field_type="title",
                        selector=sel,
                        locator=loc,
                        confidence=0.9 if "title" in sel else 0.75,
                    )
                    break
            except Exception:
                continue

        # 3. Detect Description Field (including rich text / contenteditable)
        for sel in self.DESCRIPTION_SELECTORS:
            loc = page.locator(sel).first
            try:
                if await loc.count() > 0 and await loc.is_visible():
                    is_ce = False
                    tag_name = await loc.evaluate("el => el.tagName.toLowerCase()")
                    if tag_name == "div" or await loc.get_attribute("contenteditable") == "true":
                        is_ce = True
                    report.description_field = FormFieldMatch(
                        field_type="description",
                        selector=sel,
                        locator=loc,
                        confidence=0.85 if not is_ce else 0.8,
                        element_tag=tag_name,
                        is_contenteditable=is_ce,
                    )
                    break
            except Exception:
                continue

        # 4. Detect Tags Field
        for sel in self.TAGS_SELECTORS:
            loc = page.locator(sel).first
            try:
                if await loc.count() > 0 and await loc.is_visible():
                    report.tags_field = FormFieldMatch(
                        field_type="tags",
                        selector=sel,
                        locator=loc,
                        confidence=0.8,
                    )
                    break
            except Exception:
                continue

        # 5. Detect Category Dropdown
        try:
            selects = page.locator("select")
            select_count = await selects.count()
            for i in range(select_count):
                sel_loc = selects.nth(i)
                if await sel_loc.is_visible():
                    options_text = (await sel_loc.inner_text()).lower()
                    if any(cat in options_text for cat in self.PREFERRED_CATEGORIES):
                        report.category_select = FormFieldMatch(
                            field_type="category",
                            selector=f"select:nth-of-type({i+1})",
                            locator=sel_loc,
                            confidence=0.85,
                            element_tag="select",
                        )
                        break
        except Exception:
            pass

        # 6. Detect Submit Button
        for sel in self.SUBMIT_SELECTORS:
            loc = page.locator(sel).first
            try:
                if await loc.count() > 0 and await loc.is_visible():
                    report.submit_button = FormFieldMatch(
                        field_type="submit",
                        selector=sel,
                        locator=loc,
                        confidence=0.9,
                        element_tag="button",
                    )
                    break
            except Exception:
                continue

        # Calculate scores
        matches = [
            report.url_field,
            report.title_field,
            report.description_field,
            report.tags_field,
            report.category_select,
            report.submit_button,
        ]
        active_matches = [m for m in matches if m is not None]
        report.detected_fields_count = len(active_matches)
        if active_matches:
            report.confidence_score = round(
                sum(m.confidence for m in active_matches) / len(active_matches), 2
            )

        return report

    async def fill_form_automatically(
        self,
        browser: VisibleBrowser,
        draft: Draft,
        report: FormDetectionReport | None = None,
        human_like: bool = True,
    ) -> tuple[bool, str | None]:
        """Automatically fills the detected form using visible highlighting and human simulation."""
        page = browser.page
        if not page:
            return False, "Page is unavailable"

        if not report:
            report = await self.detect_form(page)

        if not report.is_usable:
            return False, "No recognized submission form fields found on page"

        try:
            # 1. Fill Target URL
            if report.url_field:
                await browser.highlight_and_fill(
                    report.url_field.locator,
                    draft.target_url,
                    "target URL",
                    human_like=human_like,
                )

            # 2. Fill Title
            if report.title_field:
                await browser.highlight_and_fill(
                    report.title_field.locator,
                    draft.title,
                    "title",
                    human_like=human_like,
                )

            # 3. Fill Description (handles textarea or contenteditable div)
            if report.description_field:
                desc_match = report.description_field
                await browser.highlight(desc_match.locator)
                if desc_match.is_contenteditable:
                    await desc_match.locator.click()
                    await desc_match.locator.fill(draft.description)
                else:
                    await desc_match.locator.fill(draft.description)
                await browser.unhighlight(desc_match.locator)

            # 4. Fill Tags
            if report.tags_field and draft.tags:
                await browser.highlight_and_fill(
                    report.tags_field.locator,
                    draft.tags,
                    "tags",
                    human_like=human_like,
                )

            # 5. Select Category if available
            if report.category_select:
                select_loc = report.category_select.locator
                await browser.highlight(select_loc)
                options = await select_loc.locator("option").all()
                selected = False
                for opt in options:
                    opt_val = (await opt.get_attribute("value") or "").lower()
                    opt_text = (await opt.inner_text()).lower()
                    if any(cat in opt_val or cat in opt_text for cat in self.PREFERRED_CATEGORIES):
                        raw_val = await opt.get_attribute("value")
                        if raw_val is not None:
                            await select_loc.select_option(value=raw_val)
                            selected = True
                            break
                await browser.unhighlight(select_loc)

            return True, None
        except Exception as exc:
            logger.error("Auto form fill encountered an error: %s", exc)
            return False, f"Auto form fill failed: {exc}"
