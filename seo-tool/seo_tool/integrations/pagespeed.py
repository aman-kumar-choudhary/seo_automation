"""PageSpeed Insights v5: CrUX field data (real users) + Lighthouse lab scores.
Optional API key via env SEO_PAGESPEED_API_KEY (recommended for more than a few URLs)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from ..logging_setup import log
from ..resilience import call_with_retry

logger = logging.getLogger("seo_tool.pagespeed")
ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CATEGORIES = ("performance", "seo", "accessibility", "best-practices")


def run_pagespeed(urls: list[str], strategy: str = "mobile", timeout: float = 120.0) -> dict[str, dict[str, Any]]:
    key = os.environ.get("SEO_PAGESPEED_API_KEY")
    session = requests.Session()
    out: dict[str, dict[str, Any]] = {}
    for url in urls:
        params = [("url", url), ("strategy", strategy)] + [("category", c) for c in CATEGORIES]
        if key:
            params.append(("key", key))
        try:
            resp = call_with_retry(lambda: session.get(ENDPOINT, params=params, timeout=timeout))
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            log(logger, logging.WARNING, "pagespeed failed", url=url, error=str(exc))
            out[url] = {"error": str(exc)}
            continue
        le = data.get("loadingExperience") or {}
        lh = data.get("lighthouseResult") or {}
        out[url] = {
            "strategy": strategy,
            "field": {
                "scope": "origin" if le.get("origin_fallback") else "page",
                "overall": le.get("overall_category"),
                "metrics": {k: {"p75": v.get("percentile"), "category": v.get("category")}
                            for k, v in (le.get("metrics") or {}).items()},
            },
            "lab": {cid: round(c["score"] * 100) for cid, c in (lh.get("categories") or {}).items()
                    if c.get("score") is not None},
            "lighthouse_version": lh.get("lighthouseVersion"),
            "runtime_error": (lh.get("runtimeError") or {}).get("message"),
        }
        time.sleep(1.0)
    return out
