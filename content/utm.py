"""Campaign UTM Parameter Generator for Innovions SEO Referral Tracking.

Constructs consistent, structured UTM tracking parameters on target URLs:
https://innovions.org/?utm_source={domain}&utm_medium=social_bookmark&utm_campaign=rfid_seo&utm_content={cluster}
Enables precise attribution in Google Analytics 4, Plausible, and server access logs.
"""
from __future__ import annotations

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def build_utm_url(
    base_url: str = "https://innovions.org/",
    domain: str = "general",
    cluster_name: str = "rfid",
    campaign: str = "rfid_seo",
    medium: str = "social_bookmark",
) -> str:
    """Attaches standardized UTM attribution parameters to base target URL."""
    clean_domain = domain.strip().lower().removeprefix("www.")
    clean_cluster = cluster_name.strip().lower().replace(" ", "-").replace("&", "and")

    parsed = urlparse(base_url.strip())
    query_params = parse_qs(parsed.query)

    query_params["utm_source"] = [clean_domain]
    query_params["utm_medium"] = [medium]
    query_params["utm_campaign"] = [campaign]
    query_params["utm_content"] = [clean_cluster]

    new_query = urlencode(query_params, doseq=True)
    return urlunparse((
        parsed.scheme or "https",
        parsed.netloc or "innovions.org",
        parsed.path or "/",
        parsed.params,
        new_query,
        parsed.fragment,
    ))
