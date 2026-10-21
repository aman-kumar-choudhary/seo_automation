from __future__ import annotations

import gzip
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from .bots import bot_access
from .config import Config
from .http import FetchResult, Fetcher
from .logging_setup import log
from .parser import PageData, parse_html
from .urls import host_of, in_scope, is_asset, normalize_url, origin_of

logger = logging.getLogger("seo_tool.crawler")
MAX_SITEMAP_FILES = 50
MAX_SITEMAP_URLS = 50_000
SITEMAP_MAX_BYTES = 50 * 1024 * 1024
_CHALLENGE_MARKERS = (b"challenge-platform", b"cf-chl-", b"just a moment...", b"captcha", b"_incapsula_resource",
                      b"ddos-guard", b"attention required")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


@dataclass
class RobotsInfo:
    url: str
    status: int | None
    error: str | None
    sitemaps: list[str]
    googlebot_allowed_start: bool
    content_preview: str
    ai_bots: dict[str, bool] = field(default_factory=dict)


@dataclass
class SitemapInfo:
    locations: list[str] = field(default_factory=list)
    urls: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)
    from_robots: bool = False


@dataclass
class LinkStatus:
    url: str
    status: int | None
    final_url: str
    error: str | None
    redirects: int
    blocked: bool


@dataclass
class SiteData:
    start_url: str
    root_host: str
    config: Config
    pages: dict[str, PageData] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)  # final_url -> page key
    robots: RobotsInfo | None = None
    sitemap: SitemapInfo = field(default_factory=SitemapInfo)
    blocked: set[str] = field(default_factory=set)
    link_status: dict[str, LinkStatus] = field(default_factory=dict)
    unchecked_links: int = 0
    http_check: LinkStatus | None = None
    limit_reached: bool = False
    interrupted: bool = False
    started_at: float = 0.0
    finished_at: float = 0.0
    requests: int = 0
    skipped_by_rules: int = 0
    llms_txt: bool | None = None
    extras: dict[str, dict[str, Any]] = field(default_factory=dict)  # pagespeed, gsc, plugin data

    def lookup(self, url: str) -> tuple[PageData | None, bool]:
        """(page, redirects): redirects is True if requesting `url` itself redirects."""
        if url in self.pages:
            page = self.pages[url]
            return page, bool(page.redirect_chain)
        key = self.aliases.get(url)
        return (self.pages[key], False) if key else (None, False)


class Crawler:
    def __init__(self, cfg: Config, fetcher: Fetcher | None = None) -> None:
        self.cfg = cfg
        self.fetcher = fetcher or Fetcher(cfg)
        self.renderer: Any = None
        self._assets: set[str] = set()
        self._exclude = [re.compile(p) for p in cfg.exclude_patterns]

    def crawl(self, start_url: str, state: Any = None) -> SiteData:
        start = normalize_url(start_url, strip_tracking=self.cfg.strip_tracking_params)
        if not start:
            raise ValueError(f"invalid http(s) URL: {start_url}")
        snap = state.load(start) if state else None
        frontier: list[Any] | None = None
        if snap:
            site, *frontier = snap
            self._assets = frontier.pop()
            site.config, site.interrupted, site.limit_reached = self.cfg, False, False
            log(logger, logging.INFO, "resuming crawl", pages=len(site.pages),
                queued=len(frontier[0]) + len(frontier[1]))
        else:
            site = SiteData(start_url=start, root_host=host_of(start), config=self.cfg, started_at=time.time())
            self._assets = set()
        if self.cfg.render_js:
            from .render import JsRenderer
            self.renderer = JsRenderer(self.cfg)
        completed = False
        try:
            if frontier is None:
                site.robots = self._load_robots(start)
                site.sitemap = self._load_sitemaps(start, site)
                site.llms_txt = self._probe_llms_txt(start)
                frontier = list(self._seed(site))
            self._crawl_pages(site, *frontier, state=state)
            self._check_links(site)
            site.http_check = self._check_http_redirect(start)
            completed = True
        except KeyboardInterrupt:
            site.interrupted = True
            log(logger, logging.WARNING, "crawl interrupted; checkpoint saved, use --resume to continue")
        finally:
            self._build_graph(site)
            if self.renderer:
                self.renderer.close()
            site.finished_at = time.time()
            site.requests += self.fetcher.request_count
            if state and completed and not site.limit_reached:
                state.clear(start)
        return site

    def _crawlable(self, url: str, check_params: bool = True) -> bool:
        if any(r.search(url) for r in self._exclude):
            return False
        if check_params and self.cfg.max_query_params:
            if len(parse_qsl(urlsplit(url).query, keep_blank_values=True)) > self.cfg.max_query_params:
                return False
        return True

    # ---------- discovery ----------
    def _load_robots(self, start: str) -> RobotsInfo:
        rp = self.fetcher.robots_for(start)
        origin = origin_of(start)
        res = self.fetcher.robots_raw.get(origin)
        ok = bool(res and res.status and 200 <= res.status < 300)
        return RobotsInfo(
            url=origin + "/robots.txt", status=res.status if res else None, error=res.error if res else None,
            sitemaps=list(rp.sitemaps), googlebot_allowed_start=bool(rp.can_fetch(start, "Googlebot")),
            content_preview=res.text()[:2000] if ok and res else "", ai_bots=bot_access(rp, start),
        )

    def _probe_llms_txt(self, start: str) -> bool | None:
        if not self.cfg.check_llms_txt:
            return None
        res = self.fetcher.fetch(origin_of(start) + "/llms.txt", max_bytes=200_000)
        if res.blocked_by_robots or res.error:
            return None
        return res.status == 200 and res.content_type.startswith("text/") and res.content_type != "text/html"

    def _load_sitemaps(self, start: str, site: SiteData) -> SitemapInfo:
        info = SitemapInfo()
        candidates = list(site.robots.sitemaps) if site.robots else []
        info.from_robots = bool(candidates)
        if not candidates:
            candidates = [origin_of(start) + "/sitemap.xml"]
        queue, seen = deque(candidates), set()
        while queue and len(seen) < MAX_SITEMAP_FILES and len(info.urls) < MAX_SITEMAP_URLS:
            sm_url = queue.popleft()
            if sm_url in seen:
                continue
            seen.add(sm_url)
            res = self.fetcher.fetch(sm_url, max_bytes=SITEMAP_MAX_BYTES)
            if res.status != 200 or res.error:
                if info.from_robots or res.status not in (404, 410):
                    info.errors.append(f"{sm_url}: {res.error or f'HTTP {res.status}'}")
                continue
            body = res.body
            if sm_url.endswith(".gz") or body[:2] == b"\x1f\x8b":
                try:
                    body = gzip.decompress(body)
                except OSError as exc:
                    info.errors.append(f"{sm_url}: invalid gzip ({exc})")
                    continue
            try:
                root = ET.fromstring(body)
            except ET.ParseError as exc:
                info.errors.append(f"{sm_url}: invalid XML ({exc})")
                continue
            info.locations.append(sm_url)
            kind = _local(root.tag)
            locs = [(el.text or "").strip() for child in root for el in child if _local(el.tag) == "loc"]
            if kind == "sitemapindex":
                queue.extend(loc for loc in locs if loc)
            elif kind == "urlset":
                for loc in locs:
                    u = normalize_url(loc, strip_tracking=self.cfg.strip_tracking_params)
                    if u:
                        info.urls.add(u)
            else:
                info.errors.append(f"{sm_url}: unexpected root element <{kind}>")
        return info

    def _seed(self, site: SiteData) -> tuple[deque, deque, set]:
        cfg = self.cfg
        queue: deque[tuple[str, int]] = deque([(site.start_url, 0)])
        sitemap_queue: deque[tuple[str, int]] = deque()
        seen = {site.start_url}
        if cfg.use_sitemap_seeds:
            for u in sorted(site.sitemap.urls):
                if u in seen or not in_scope(u, site.root_host, cfg.include_subdomains) or is_asset(u):
                    continue
                seen.add(u)
                if self._crawlable(u, check_params=False):
                    sitemap_queue.append((u, cfg.max_depth))  # sitemap-only pages: don't expand deeply
                else:
                    site.skipped_by_rules += 1
        return queue, sitemap_queue, seen

    # ---------- crawl ----------
    def _crawl_pages(self, site: SiteData, queue: deque, sitemap_queue: deque, seen: set,
                     state: Any = None) -> None:
        cfg = self.cfg

        def checkpoint() -> None:
            if state:
                state.save(site.start_url, (site, queue, sitemap_queue, seen, self._assets))

        try:
            while (queue or sitemap_queue) and len(site.pages) < cfg.max_pages:
                url, depth = queue.popleft() if queue else sitemap_queue.popleft()
                res = self.fetcher.fetch(url)
                if res.blocked_by_robots:
                    site.blocked.add(url)
                    continue
                page = self._build_page(res, depth, site)
                if not site.pages:
                    if page.bot_challenge:
                        log(logger, logging.WARNING, "start URL returned a bot challenge; the site blocks "
                            "automated access. This tool does not bypass challenges.", url=url)
                    if not in_scope(page.final_url, site.root_host, cfg.include_subdomains):
                        log(logger, logging.WARNING, "start URL redirects off-host; adopting final host",
                            start=url, final=page.final_url)
                        site.root_host = host_of(page.final_url)
                        page = self._build_page(res, depth, site)
                site.pages[url] = page
                if page.final_url != url:
                    site.aliases.setdefault(page.final_url, url)
                    seen.add(page.final_url)

                if page.ok and in_scope(page.final_url, site.root_host, cfg.include_subdomains) \
                        and not page.is_nofollow:
                    for link in page.links:
                        target = link.url
                        if target in seen or not in_scope(target, site.root_host, cfg.include_subdomains):
                            continue
                        seen.add(target)
                        if is_asset(target):
                            self._assets.add(target)
                        elif not self._crawlable(target):
                            site.skipped_by_rules += 1
                        elif depth + 1 <= cfg.max_depth:
                            queue.append((target, depth + 1))

                if len(site.pages) % 25 == 0:
                    log(logger, logging.INFO, "crawl progress", pages=len(site.pages),
                        queued=len(queue) + len(sitemap_queue), requests=self.fetcher.request_count)
                    checkpoint()
        finally:
            checkpoint()
        site.limit_reached = bool(queue or sitemap_queue)

    def _new_page(self, res: FetchResult, depth: int) -> PageData:
        final = normalize_url(res.final_url, strip_tracking=self.cfg.strip_tracking_params) or res.final_url
        if res.truncated:
            log(logger, logging.WARNING, "response truncated at max_response_bytes", url=res.url)
        challenge = res.headers.get("cf-mitigated", "").lower() == "challenge" or (
            res.status in (403, 429, 503) and any(m in res.body[:20000].lower() for m in _CHALLENGE_MARKERS))
        return PageData(
            url=res.url, final_url=final, depth=depth, status=res.status,
            redirect_chain=list(res.redirect_chain), headers=res.headers, content_type=res.content_type,
            elapsed=round(res.elapsed, 3), ttfb=round(res.ttfb, 3), html_bytes=len(res.body),
            error=res.error, x_robots_tag=res.headers.get("x-robots-tag", ""), bot_challenge=challenge,
        )

    def _build_page(self, res: FetchResult, depth: int, site: SiteData) -> PageData:
        page = self._new_page(res, depth)
        if not (page.ok and in_scope(page.final_url, site.root_host, self.cfg.include_subdomains)):
            return page
        kw, strip = self.cfg.target_keywords, self.cfg.strip_tracking_params
        try:
            parse_html(page, res.body, kw, strip, encoding=res.charset)
            if self.renderer:
                self.fetcher.wait_turn(page.final_url)
                html = self.renderer.render(page.final_url)
                if html:
                    rendered = self._new_page(res, depth)
                    parse_html(rendered, html, kw, strip)
                    rendered.rendered = True
                    rendered.raw_word_count = page.word_count
                    page = rendered
        except Exception as exc:  # never let one bad page kill the crawl
            page.error = f"parse error: {type(exc).__name__}: {exc}"
            log(logger, logging.ERROR, "parse failed", url=page.url, error=page.error)
        return page

    # ---------- post-crawl ----------
    def _check_links(self, site: SiteData) -> None:
        targets = sorted(self._assets)
        if self.cfg.check_external_links:
            external = {lk.url for p in site.pages.values() for lk in p.links
                        if not in_scope(lk.url, site.root_host, self.cfg.include_subdomains)}
            targets += sorted(external)
        budget = self.cfg.max_link_checks
        for url in targets[:budget]:
            if url in site.link_status:
                continue
            res = self.fetcher.check_link(url)
            site.link_status[url] = LinkStatus(url, res.status, res.final_url, res.error,
                                               len(res.redirect_chain), res.blocked_by_robots)
        site.unchecked_links = max(0, len(targets) - budget)

    def _check_http_redirect(self, start: str) -> LinkStatus | None:
        p = urlsplit(start)
        if p.scheme != "https":
            return None
        http_url = urlunsplit(("http", p.netloc, "/", "", ""))
        res = self.fetcher.check_link(http_url)
        return LinkStatus(http_url, res.status, res.final_url, res.error, len(res.redirect_chain),
                          res.blocked_by_robots)

    @staticmethod
    def _build_graph(site: SiteData) -> None:
        graph: dict[str, set[str]] = {}
        inlinks: dict[str, set[str]] = defaultdict(set)
        for key, page in site.pages.items():
            targets = set()
            for link in page.links:
                tkey = link.url if link.url in site.pages else site.aliases.get(link.url)
                if tkey and tkey != key:
                    targets.add(tkey)
            graph[key] = targets
            for t in targets:
                inlinks[t].add(key)
        for key, page in site.pages.items():
            page.inlinks = len(inlinks.get(key, ()))
            page.in_sitemap = key in site.sitemap.urls or page.final_url in site.sitemap.urls
        if site.start_url in site.pages:
            depth = {site.start_url: 0}
            q = deque([site.start_url])
            while q:
                cur = q.popleft()
                for nxt in graph.get(cur, ()):
                    if nxt not in depth:
                        depth[nxt] = depth[cur] + 1
                        q.append(nxt)
            for key, page in site.pages.items():
                page.click_depth = depth.get(key)
