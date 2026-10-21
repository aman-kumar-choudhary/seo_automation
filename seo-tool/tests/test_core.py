import pytest

from seo_tool.changes import ConflictError, apply_field, validate
from seo_tool.parser import PageData, parse_html
from seo_tool.urls import duplicate_key, normalize_url


def _page():
    return PageData(url="https://ex.com/", final_url="https://ex.com/", depth=0, status=200, content_type="text/html")


def test_normalize_url():
    assert normalize_url("HTTP://Example.com:80/a?utm_source=x&b=1#frag") == "http://example.com/a?b=1"
    assert normalize_url("mailto:a@b.c") is None
    assert normalize_url("../x", "https://ex.com/a/b/") == "https://ex.com/a/x"
    assert duplicate_key("https://www.Ex.com/A/index.html") == duplicate_key("http://ex.com/a/")


def test_parse_html():
    html = ('<html lang="en"><head><title> Hi </title><meta name="robots" content="noindex">'
            '<link rel="canonical" href="/c"></head><body><h1>A</h1><a href="/x">X</a><img src="i.png"></body></html>')
    p = _page()
    parse_html(p, html)
    assert p.title == "Hi" and p.is_noindex and p.canonical == "https://ex.com/c"
    assert p.links[0].url == "https://ex.com/x" and p.images[0].alt is None and p.lang == "en"


def test_apply_title_and_conflict():
    doc = "<html><head><title>Old</title></head></html>"
    assert "<title>New &amp; better</title>" in apply_field(doc, "title", "Old", "New & better")
    with pytest.raises(ConflictError):
        apply_field(doc, "title", "Different", "New")


def test_meta_description_insert_escapes():
    out = apply_field("<html><head></head></html>", "meta_description", None, 'Say "hi"')
    assert 'content="Say &quot;hi&quot;"' in out


def test_validate_blocks_keyword_stuffing():
    errors, _ = validate("Shoes shoes cheap shoes", None, "title", set(), ["shoes"])
    assert errors
