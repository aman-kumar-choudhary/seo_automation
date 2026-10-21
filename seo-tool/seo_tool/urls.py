from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMS = {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid", "yclid", "_ga"}
ASSET_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".ico", ".zip", ".gz",
    ".rar", ".mp3", ".mp4", ".webm", ".mov", ".avi", ".doc", ".docx", ".xls", ".xlsx", ".ppt",
    ".pptx", ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".xml", ".json", ".txt",
)


def normalize_url(url: str, base: str | None = None, strip_tracking: bool = True) -> str | None:
    """Absolute, fragment-free, lowercase scheme/host, default port removed. None if not http(s)."""
    try:
        url = url.strip()
        if base:
            url = urljoin(base, url)
        p = urlsplit(url)
        scheme = p.scheme.lower()
        if scheme not in ("http", "https"):
            return None
        host = (p.hostname or "").lower().rstrip(".")
        if not host:
            return None
        port = p.port
    except ValueError:
        return None
    if ":" in host:
        host = f"[{host}]"
    netloc = host if port is None or (scheme, port) in (("http", 80), ("https", 443)) else f"{host}:{port}"
    path = (p.path or "/").replace(" ", "%20")
    query = p.query
    if strip_tracking and query:
        pairs = parse_qsl(query, keep_blank_values=True)
        kept = [(k, v) for k, v in pairs if not (k.lower().startswith("utm_") or k.lower() in TRACKING_PARAMS)]
        if len(kept) != len(pairs):
            query = urlencode(kept, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def origin_of(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def bare_host(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def in_scope(url: str, root_host: str, include_subdomains: bool = False) -> bool:
    h, r = bare_host(host_of(url)), bare_host(root_host)
    return h == r or (include_subdomains and h.endswith("." + r))


def is_asset(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(ASSET_EXTENSIONS)


def duplicate_key(url: str) -> str:
    """Key that collapses common duplicate-URL variants (case, www, slash, index file, param order)."""
    p = urlsplit(url.lower())
    path = p.path
    for idx in ("/index.html", "/index.htm", "/index.php", "/default.aspx"):
        if path.endswith(idx):
            path = path[: -len(idx) + 1]
    path = path.rstrip("/") or "/"
    query = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
    return f"{bare_host(p.hostname or '')}{path}?{query}"
