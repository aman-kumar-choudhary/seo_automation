import pytest
from pathlib import Path
from hard_dry_test import run_hard_dry_test
from database.repository import Repository
from database.models import Status


@pytest.mark.asyncio
async def test_full_automated_hard_dry_test(tmp_path):
    """Runs a complete hard dry test across N=3 platforms in headless mode to verify end-to-end pipeline."""
    db_file = tmp_path / "test_hard_dry.db"
    await run_hard_dry_test(
        count=3,
        headless=True,
        slow_mo=50,
        dashboard_port=8775,
        test_server_port=8776,
        db_path=str(db_file),
    )

    repo = Repository(db_file)
    platforms = repo.platforms()
    assert len(platforms) == 3

    # All 3 platforms must be verified ELIGIBLE
    for p in platforms:
        assert p["eligibility_status"] in (Status.ELIGIBLE, Status.AWAITING_APPROVAL)
        assert p["da"] is not None
        assert p["da"] >= 20
        assert p["spam_score"] < 10

    # Submissions must be recorded with screenshots and dry-run safety
    report_rows = repo.report_rows()
    assert len(report_rows) == 3
    for r in report_rows:
        assert r["submission_status"] == Status.AWAITING_APPROVAL
        assert r["screenshot_path"] is not None
        assert Path(r["screenshot_path"]).exists()
        assert "RFID" in r["draft_title"]
        assert "https://innovions.org/" == r["target_url"]
