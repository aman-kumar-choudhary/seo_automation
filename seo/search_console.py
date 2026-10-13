"""Google Search Console API client and search visibility analytics."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from .models import SearchConsoleMetrics

logger = logging.getLogger(__name__)


class SearchConsoleClient:
    """Retrieves search performance metrics (clicks, impressions, CTR, position) when API credentials exist."""

    def __init__(
        self,
        target_site_url: str = "https://innovions.org/",
        credentials_file: str | Path | None = None,
        api_token: str | None = None,
    ):
        self.site_url = target_site_url
        self.credentials_file = credentials_file or os.getenv("GSC_CREDENTIALS_PATH")
        self.api_token = api_token or os.getenv("GSC_API_TOKEN")

    async def fetch_performance(self, days: int = 28) -> SearchConsoleMetrics:
        """Fetches organic search performance or returns clear offline status if unconfigured."""
        # 1. Check if authenticated API credentials are provided
        if not self.credentials_file and not self.api_token:
            return SearchConsoleMetrics(
                configured=False,
                total_clicks=0,
                total_impressions=0,
                average_ctr=0.0,
                average_position=0.0,
                details=(
                    "Google Search Console API credentials not configured (GSC_CREDENTIALS_PATH / GSC_API_TOKEN unset). "
                    "Set credentials in .env to retrieve verified Google search clicks, impressions, CTR, and position."
                ),
            )

        # 2. Live API connection path
        try:
            import httpx
            headers = {"Authorization": f"Bearer {self.api_token}"}
            api_endpoint = f"https://www.googleapis.com/webmasters/v3/sites/{self.site_url}/searchAnalytics/query"
            payload = {
                "startDate": "2026-09-15",
                "endDate": "2026-10-12",
                "dimensions": ["query", "page"],
                "rowLimit": 10,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(api_endpoint, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("rows", [])
                    total_clicks = sum(r.get("clicks", 0) for r in rows)
                    total_impr = sum(r.get("impressions", 0) for r in rows)
                    avg_ctr = round((total_clicks / total_impr * 100), 2) if total_impr > 0 else 0.0
                    avg_pos = round(sum(r.get("position", 0) for r in rows) / max(1, len(rows)), 1)
                    return SearchConsoleMetrics(
                        configured=True,
                        total_clicks=total_clicks,
                        total_impressions=total_impr,
                        average_ctr=avg_ctr,
                        average_position=avg_pos,
                        top_queries=[{"query": r["keys"][0], "clicks": r["clicks"], "position": r["position"]} for r in rows if "keys" in r],
                        details="Verified metrics retrieved from Google Search Console API.",
                    )
                else:
                    return SearchConsoleMetrics(
                        configured=False,
                        details=f"Search Console API returned HTTP {resp.status_code}: {resp.text[:120]}",
                    )
        except Exception as exc:
            logger.warning("Search Console API query error: %s", exc)
            return SearchConsoleMetrics(
                configured=False,
                details=f"Search Console API query encountered an error: {exc}",
            )
