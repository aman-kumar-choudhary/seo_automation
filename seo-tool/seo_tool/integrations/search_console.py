"""Search Console URL Inspection API (Google's real index status).
Needs `pip install 'seo-tool[google]'` and a service-account JSON key whose e-mail is added as a
user on the Search Console property. siteUrl: 'https://www.example.com/' or 'sc-domain:example.com'."""
from __future__ import annotations

import logging
import time
from typing import Any

from ..logging_setup import log
from ..resilience import call_with_retry

logger = logging.getLogger("seo_tool.gsc")
ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
FIELDS = ("verdict", "coverageState", "robotsTxtState", "indexingState", "pageFetchState",
          "lastCrawlTime", "crawledAs", "googleCanonical", "userCanonical")


def inspect_urls(urls: list[str], site_url: str, credentials_file: str) -> dict[str, dict[str, Any]]:
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("Search Console needs: pip install 'seo-tool[google]'") from exc
    creds = service_account.Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    session = AuthorizedSession(creds)
    out: dict[str, dict[str, Any]] = {}
    for url in urls:
        resp = call_with_retry(lambda: session.post(ENDPOINT, json={"inspectionUrl": url, "siteUrl": site_url},
                                                    timeout=60))
        if resp.status_code in (401, 403):
            raise RuntimeError(f"Search Console denied access ({resp.status_code}). Add the service account "
                               f"as a user on property {site_url}.")
        if resp.status_code != 200:
            log(logger, logging.WARNING, "inspection failed", url=url, status=resp.status_code,
                body=resp.text[:300])
            continue
        result = (resp.json().get("inspectionResult") or {}).get("indexStatusResult") or {}
        out[url] = {k: result.get(k) for k in FIELDS}
        time.sleep(0.5)
    return out
