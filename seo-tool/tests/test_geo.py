from protego import Protego

from seo_tool.bots import bot_access
from seo_tool.checks.international import valid_hreflang
from seo_tool.parser import PageData, count_words, parse_html


def _page():
    return PageData(url="https://ex.com/", final_url="https://ex.com/", depth=0, status=200, content_type="text/html")


def test_snippet_directives():
    p = _page()
    p.meta_robots = "max-snippet:20, max-image-preview:large"
    assert p.max_snippet == 20 and not p.is_noindex and not p.is_nosnippet
    p.x_robots_tag = "googlebot: nosnippet"
    assert p.is_nosnippet


def test_ai_bot_access():
    rp = Protego.parse("User-agent: GPTBot\nDisallow: /\n")
    access = bot_access(rp, "https://ex.com/")
    assert access["GPTBot"] is False and access["OAI-SearchBot"] is True


def test_cjk_word_count():
    assert count_words("这是一个关于跑步鞋的详细介绍页面内容") > 5
    assert count_words("plain english words here") == 4


def test_hreflang_codes():
    assert valid_hreflang("en") and valid_hreflang("en-GB") and valid_hreflang("x-default")
    assert not valid_hreflang("en_GB") and not valid_hreflang("english")


def test_schema_author_and_dates():
    html = ('<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Article",'
            '"headline":"How to choose trail shoes","author":{"@type":"Person","name":"Jane Doe"},'
            '"datePublished":"2026-01-05"}</script></head><body><h1>How to choose trail shoes</h1>'
            '<p>Text</p></body></html>')
    p = _page()
    parse_html(p, html)
    assert p.is_article and p.authors == ["Jane Doe"] and p.date_published == "2026-01-05"
    assert "how to choose trail shoes" in p.visible_text
