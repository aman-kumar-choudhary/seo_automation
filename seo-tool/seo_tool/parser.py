from __future__ import annotations

import codecs
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from bs4 import BeautifulSoup

from .urls import normalize_url

try:
    import lxml  # noqa: F401
    _PARSER = "lxml"
except ImportError:
    _PARSER = "html.parser"

_WORD_RE = re.compile(r"\w+", re.UNICODE)
# Scripts usually written without spaces between words (Chinese, Japanese, Thai). Korean uses spaces.
_NOSPACE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u0e00-\u0e7f]")
_QUESTION_RE = re.compile(r"[?？]\s*$|^(what|how|why|when|where|who|which|can|does|do|is|are|should|will)\b", re.I)
_LINK_HEADER_CANONICAL = re.compile(r'<([^>]+)>\s*;\s*rel="?canonical"?', re.I)
_JS_ROOT_IDS = ("root", "app", "__next", "__nuxt", "svelte")
_DIRECTIVE_KEYS = {"max-snippet", "max-image-preview", "max-video-preview", "unavailable_after"}
ARTICLE_TYPES = {"Article", "BlogPosting", "NewsArticle", "TechArticle", "Report", "ScholarlyArticle"}
VISIBLE_TEXT_CAP = 50_000


@dataclass
class Link:
    url: str
    text: str
    rel: list[str]


@dataclass
class Image:
    src: str
    alt: str | None
    has_dimensions: bool


@dataclass
class PageData:
    url: str
    final_url: str
    depth: int
    status: int | None
    redirect_chain: list[tuple[str, int]] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str = ""
    elapsed: float = 0.0
    ttfb: float = 0.0
    html_bytes: int = 0
    error: str | None = None
    title: str | None = None
    title_count: int = 0
    meta_description: str | None = None
    meta_robots: str = ""
    x_robots_tag: str = ""
    canonicals: list[str] = field(default_factory=list)
    lang: str | None = None
    viewport: str | None = None
    headings: list[tuple[int, str]] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    json_ld: list[Any] = field(default_factory=list)
    json_ld_errors: list[str] = field(default_factory=list)
    has_microdata: bool = False
    open_graph: dict[str, str] = field(default_factory=dict)
    twitter: dict[str, str] = field(default_factory=dict)
    hreflang: list[tuple[str, str]] = field(default_factory=list)
    word_count: int = 0
    raw_word_count: int | None = None
    content_hash: str | None = None
    simhash: int | None = None
    first_paragraph: str | None = None
    keyword_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    script_count: int = 0
    blocking_scripts: int = 0
    empty_js_root: bool = False
    rendered: bool = False
    in_sitemap: bool = False
    inlinks: int = 0
    click_depth: int | None = None
    # GEO / robustness signals
    data_nosnippet: int = 0
    question_headings: int = 0
    authors: list[str] = field(default_factory=list)
    date_published: str | None = None
    date_modified: str | None = None
    visible_text: str = ""      # normalized lowercase words, capped at VISIBLE_TEXT_CAP
    bot_challenge: bool = False

    @property
    def h1s(self) -> list[str]:
        return [t for lvl, t in self.headings if lvl == 1]

    @property
    def canonical(self) -> str | None:
        return self.canonicals[0] if self.canonicals else None

    @property
    def robots_directives(self) -> set[str]:
        tokens: set[str] = set()
        for part in f"{self.meta_robots},{self.x_robots_tag}".split(","):
            part = part.strip().lower()
            if ":" in part:
                key, rest = part.split(":", 1)
                if key.strip() not in _DIRECTIVE_KEYS:  # "googlebot: noindex" style user-agent prefix
                    part = rest.strip()
            if part:
                tokens.add(part.replace(" ", ""))
        return tokens

    @property
    def max_snippet(self) -> int | None:
        for t in self.robots_directives:
            if t.startswith("max-snippet:"):
                try:
                    return int(t.split(":", 1)[1])
                except ValueError:
                    return None
        return None

    @property
    def is_nosnippet(self) -> bool:
        return "nosnippet" in self.robots_directives or self.max_snippet == 0

    @property
    def is_noindex(self) -> bool:
        return bool({"noindex", "none"} & self.robots_directives)

    @property
    def is_nofollow(self) -> bool:
        return bool({"nofollow", "none"} & self.robots_directives)

    @property
    def is_html(self) -> bool:
        return self.content_type in ("text/html", "application/xhtml+xml")

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.is_html and self.error is None and not self.bot_challenge

    @property
    def is_canonical_self(self) -> bool:
        return self.canonical is None or self.canonical == self.final_url

    @property
    def indexable(self) -> bool:
        return self.ok and not self.is_noindex and self.is_canonical_self

    @property
    def schema_types(self) -> list[str]:
        types: list[str] = []
        for it in iter_entities(self.json_ld):
            t = it.get("@type")
            types.extend(t if isinstance(t, list) else [t] if t else [])
        return sorted({str(t) for t in types})

    @property
    def is_article(self) -> bool:
        return bool(set(self.schema_types) & ARTICLE_TYPES) or self.open_graph.get("og:type", "").lower() == "article"


def iter_entities(json_ld: list[Any]) -> Iterator[dict[str, Any]]:
    for obj in json_ld:
        items = obj["@graph"] if isinstance(obj, dict) and isinstance(obj.get("@graph"), list) else [obj]
        for it in items:
            if isinstance(it, dict):
                yield it


def normalize_text(text: str | None) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def count_words(text: str) -> int:
    """Word count; approximate for scripts written without spaces (~2 characters per word)."""
    words = _WORD_RE.findall(text)
    nospace = len(_NOSPACE_RE.findall(text))
    if not nospace:
        return len(words)
    other = sum(1 for w in words if not _NOSPACE_RE.search(w))
    return other + max(1, nospace // 2)


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _scalar(value: Any) -> str | None:
    if isinstance(value, (str, int, float)) and str(value).strip():
        return str(value).strip()
    return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value] if value is not None else []


def _soup(html: str | bytes, encoding: str | None) -> BeautifulSoup:
    if isinstance(html, bytes) and encoding:
        try:
            codecs.lookup(encoding)
            return BeautifulSoup(html, _PARSER, from_encoding=encoding)
        except LookupError:
            pass
    return BeautifulSoup(html, _PARSER)


def parse_html(page: PageData, html: str | bytes, keywords: list[str] | None = None,
               strip_tracking: bool = True, encoding: str | None = None) -> None:
    soup = _soup(html, encoding)
    base = page.final_url
    base_tag = soup.find("base", href=True)
    if base_tag:
        base = normalize_url(base_tag["href"], page.final_url) or base
    head = soup.head or soup

    titles = head.find_all("title")
    page.title_count = len(titles)
    page.title = _clean(titles[0].get_text()) if titles else None

    robots: list[str] = []
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").strip().lower()
        prop = (meta.get("property") or "").strip().lower()
        content = _clean(meta.get("content"))
        if name == "description" and page.meta_description is None:
            page.meta_description = content
        elif name in ("robots", "googlebot"):
            robots.append(content.lower())
        elif name == "viewport":
            page.viewport = content
        elif name == "author" and content:
            page.authors.append(content)
        elif name.startswith("twitter:"):
            page.twitter.setdefault(name, content)
        if prop.startswith("og:"):
            page.open_graph.setdefault(prop, content)
        elif prop == "article:published_time" and content:
            page.date_published = page.date_published or content
        elif prop == "article:modified_time" and content:
            page.date_modified = page.date_modified or content
    page.meta_robots = ", ".join(r for r in robots if r)

    for link in soup.find_all("link", href=True):
        rels = [r.lower() for r in (link.get("rel") or [])]
        href = normalize_url(link["href"], base, strip_tracking)
        if not href:
            continue
        if "canonical" in rels:
            page.canonicals.append(href)
        elif "alternate" in rels and link.get("hreflang"):
            page.hreflang.append((link["hreflang"].strip(), href))
        elif "stylesheet" in rels:
            page.resources.append(href)
    for m in _LINK_HEADER_CANONICAL.finditer(page.headers.get("link", "")):
        href = normalize_url(m.group(1), base, strip_tracking)
        if href and href not in page.canonicals:
            page.canonicals.append(href)

    html_tag = soup.find("html")
    page.lang = (html_tag.get("lang") or None) if html_tag else None

    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        level, text = int(h.name[1]), _clean(h.get_text(" "))
        page.headings.append((level, text))
        if level in (2, 3) and _QUESTION_RE.search(text):
            page.question_headings += 1

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        url = normalize_url(href, base, strip_tracking)
        if not url:
            continue
        text = _clean(a.get_text(" ")) or _clean(a.get("aria-label") or a.get("title"))
        if not text:
            img = a.find("img", alt=True)
            text = _clean(img["alt"]) if img else ""
        page.links.append(Link(url, text, [r.lower() for r in (a.get("rel") or [])]))

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        url = normalize_url(src, base, False) if src and not src.startswith("data:") else None
        page.images.append(Image(url or src[:100], img.get("alt"), bool(img.get("width") and img.get("height"))))
        if url:
            page.resources.append(url)
    for tag in ("script", "iframe", "source", "video", "audio"):
        for el in soup.find_all(tag, src=True):
            u = normalize_url(el["src"], base, False)
            if u:
                page.resources.append(u)

    page.script_count = len(soup.find_all("script"))
    if soup.head:
        page.blocking_scripts = sum(
            1 for s in soup.head.find_all("script", src=True)
            if not s.has_attr("async") and not s.has_attr("defer") and (s.get("type") or "").lower() != "module"
        )

    for s in soup.find_all("script", type=re.compile(r"application/ld\+json", re.I)):
        raw = re.sub(r"^\s*<!--|-->\s*$", "", s.string or s.get_text() or "").strip()
        if not raw:
            page.json_ld_errors.append("empty JSON-LD block")
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            page.json_ld_errors.append(f"{exc.msg} (line {exc.lineno}, col {exc.colno})")
            continue
        page.json_ld.extend(data if isinstance(data, list) else [data])
    page.has_microdata = bool(soup.find(attrs={"itemscope": True}) or soup.find(attrs={"typeof": True}))

    for ent in iter_entities(page.json_ld):
        for a in _as_list(ent.get("author")):
            name = _scalar(a.get("name")) if isinstance(a, dict) else _scalar(a)
            if name:
                page.authors.append(_clean(name))
        page.date_published = page.date_published or _scalar(ent.get("datePublished"))
        page.date_modified = page.date_modified or _scalar(ent.get("dateModified"))
    page.authors = list(dict.fromkeys(page.authors))
    page.data_nosnippet = len(soup.find_all(attrs={"data-nosnippet": True}))

    for rid in _JS_ROOT_IDS:
        el = soup.find(id=rid)
        if el is not None and not _clean(el.get_text()):
            page.empty_js_root = True
            break

    # Visible text (for structured-data consistency) and main-content signals (boilerplate removed)
    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    page.visible_text = normalize_text((soup.body or soup).get_text(" "))[:VISIBLE_TEXT_CAP]
    main = soup.find("main") or soup.find("article") or soup.body or soup
    if main is soup.body or main is soup:
        for t in main.find_all(["nav", "header", "footer", "aside"]):
            t.decompose()
    main_text = _clean(main.get_text(" ")).lower()
    words = _WORD_RE.findall(main_text)
    page.word_count = count_words(main_text)
    if words:
        page.content_hash = hashlib.sha1(" ".join(words).encode()).hexdigest()
        page.simhash = _simhash(words)
    for p in main.find_all("p"):
        text = _clean(p.get_text(" "))
        if count_words(text) >= 12:
            page.first_paragraph = text[:1000]
            break
    if keywords:
        page.keyword_stats = keyword_stats(words, page, keywords)


def _phrase_count(text: str | None, kw_words: list[str]) -> int:
    if not text:
        return 0
    hay = " ".join(_WORD_RE.findall(text.lower()))
    return len(re.findall(r"(?=\b" + re.escape(" ".join(kw_words)) + r"\b)", hay))


def keyword_stats(words: list[str], page: PageData, keywords: list[str]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    body = " ".join(words)
    for kw in keywords:
        kw_words = _WORD_RE.findall(kw.lower())
        if not kw_words:
            continue
        count = len(re.findall(r"(?=\b" + re.escape(" ".join(kw_words)) + r"\b)", body))
        stats[kw] = {
            "content_count": count,
            "density": round(count * len(kw_words) / max(len(words), 1) * 100, 2),
            "in_title": _phrase_count(page.title, kw_words),
            "in_description": _phrase_count(page.meta_description, kw_words),
            "in_h1": any(_phrase_count(h, kw_words) for h in page.h1s),
        }
    return stats


def _simhash(words: list[str], bits: int = 64) -> int:
    feats = words if len(words) < 3 else [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    v = [0] * bits
    for f in feats[:20000]:
        h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1
    return sum(1 << i for i in range(bits) if v[i] > 0)
