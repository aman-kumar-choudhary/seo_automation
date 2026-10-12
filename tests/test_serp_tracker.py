import pytest
from unittest.mock import AsyncMock, patch
from automation.serp_tracker import SERPTracker, SERPRankingResult


@pytest.mark.asyncio
async def test_serp_tracker_parsing():
    tracker = SERPTracker(target_domain="innovions.org")

    sample_html = """
    <html>
      <body>
        <div class="result">
          <a class="result__a" href="https://example.com/item1">Item 1</a>
        </div>
        <div class="result">
          <a class="result__a" href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Finnovions.org%2Frfid-tech">Innovions RFID Solutions</a>
          <a class="result__snippet">Leading provider of RFID tracking and supply chain intelligence.</a>
        </div>
      </body>
    </html>
    """

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.text = sample_html
        mock_get.return_value = mock_resp

        res = await tracker.check_keyword("RFID")
        assert res.is_ranked is True
        assert res.rank_position == 2
        assert "innovions.org" in res.found_url
        assert "Innovions RFID Solutions" in res.page_title
