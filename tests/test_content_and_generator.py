import pytest
from database.models import Draft
from content.generator import make_draft, validate
from content.templates import get_template_style, PLATFORM_TEMPLATES


def test_make_draft_contains_keyword_and_url():
    keyword = "RFID"
    target_url = "https://innovions.org/"
    draft = make_draft("Reddit", keyword, target_url, "reddit.com")

    assert keyword.lower() in draft.title.lower() or keyword.lower() in draft.description.lower()
    assert target_url in draft.description
    assert draft.target_url == target_url

    valid, reason = validate(draft, keyword, target_url)
    assert valid is True
    assert reason is None


def test_make_draft_platform_style_variations():
    # Dev.to should get technical style
    draft_dev = make_draft("Dev.to", "RFID", "https://innovions.org/", "dev.to", seed=0)
    assert "technical" == get_template_style("Dev.to", "dev.to")
    assert "Architecture" in draft_dev.title or "Implementing" in draft_dev.title or "Protocols" in draft_dev.title

    # LinkedIn should get enterprise style
    draft_li = make_draft("LinkedIn", "RFID", "https://innovions.org/", "linkedin.com", seed=0)
    assert "enterprise" == get_template_style("LinkedIn", "linkedin.com")
    assert "Enterprise" in draft_li.title or "Supply Chain" in draft_li.title or "Logistics" in draft_li.title


def test_validate_missing_keyword():
    draft = Draft(
        title="Modern Barcode Systems Overview",
        description="Comprehensive inventory review at https://innovions.org/",
        target_url="https://innovions.org/",
        tags="inventory, barcode",
    )
    valid, reason = validate(draft, "RFID", "https://innovions.org/")
    assert valid is False
    assert "missing" in reason.lower()


def test_validate_target_url_mismatch():
    draft = Draft(
        title="RFID Solutions with Innovions",
        description="Explore RFID systems at https://different-url.com/",
        target_url="https://different-url.com/",
        tags="RFID",
    )
    valid, reason = validate(draft, "RFID", "https://innovions.org/")
    assert valid is False
    assert "target url mismatch" in reason.lower()


def test_validate_keyword_stuffing_detection():
    # Artificially repeat RFID many times
    stuffed_title = "RFID RFID RFID RFID RFID RFID RFID RFID RFID RFID"
    stuffed_desc = "RFID RFID RFID RFID RFID at https://innovions.org/ with RFID and RFID."
    draft = Draft(
        title=stuffed_title,
        description=stuffed_desc,
        target_url="https://innovions.org/",
        tags="RFID",
    )
    valid, reason = validate(draft, "RFID", "https://innovions.org/")
    assert valid is False
    assert "keyword stuffing" in reason.lower()


def test_validate_short_content():
    draft = Draft(
        title="RFID",
        description="Short https://innovions.org/",
        target_url="https://innovions.org/",
        tags="RFID",
    )
    valid, reason = validate(draft, "RFID", "https://innovions.org/")
    assert valid is False
    assert "too short" in reason.lower()
