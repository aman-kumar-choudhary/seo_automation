import pytest
from database.repository import Repository
from database.models import Status, ApprovalStatus


def test_platform_upsert_and_deduplication(tmp_path):
    repo = Repository(tmp_path / "test.db")
    item1 = {
        "name": "Dev.to",
        "domain": "dev.to",
        "registration_url": "https://dev.to/enter",
        "submission_url": "https://dev.to/new",
    }
    id1 = repo.upsert_platform(item1)
    # Re-inserting same domain with slight changes
    item2 = {
        "name": "Dev.to Community",
        "domain": "dev.to",
        "registration_url": "https://dev.to/enter",
        "submission_url": "https://dev.to/new",
    }
    id2 = repo.upsert_platform(item2)
    assert id1 == id2, "Upsert must deduplicate by domain"

    row = repo.get_platform(id1)
    assert row["name"] == "Dev.to Community"


def test_duplicate_submission_prevention(tmp_path):
    repo = Repository(tmp_path / "test.db")
    pid = repo.upsert_platform({"name": "TestPlatform", "domain": "test.org"})
    target = "https://innovions.org/"

    assert not repo.submitted(pid, target)

    # Record first published submission
    repo.record_submission(pid, None, target, Status.PUBLISHED, published_url="https://test.org/post/1")
    assert repo.submitted(pid, target) is True


def test_workflow_state_recovery(tmp_path):
    repo = Repository(tmp_path / "test.db")
    repo.save_workflow_state("last_stage", "METRICS_VERIFIED")
    repo.save_workflow_state("current_index", "4")

    assert repo.get_workflow_state("last_stage") == "METRICS_VERIFIED"
    assert repo.get_workflow_state("current_index") == "4"


def test_submission_retry_counter(tmp_path):
    repo = Repository(tmp_path / "test.db")
    pid = repo.upsert_platform({"name": "RetryPlatform", "domain": "retry.org"})
    target = "https://innovions.org/"

    # Initial failed attempt
    repo.record_submission(pid, None, target, Status.FAILED, error_message="Network error")
    sub1 = repo.db.execute("SELECT retry_count FROM submissions WHERE platform_id = ?", (pid,)).fetchone()
    assert sub1["retry_count"] == 0

    # Retry failed attempt
    repo.record_submission(pid, None, target, Status.FAILED, error_message="Network error 2")
    sub2 = repo.db.execute("SELECT retry_count FROM submissions WHERE platform_id = ?", (pid,)).fetchone()
    assert sub2["retry_count"] == 1


def test_draft_update_and_approval(tmp_path):
    repo = Repository(tmp_path / "test.db")
    pid = repo.upsert_platform({"name": "DraftPlatform", "domain": "draft.org"})
    target = "https://innovions.org/"

    repo.save_draft(pid, "Initial Title", "Initial Description", target, "RFID", True)
    draft = repo.draft_for(pid)
    assert draft["title"] == "Initial Title"
    assert draft["approval_status"] == ApprovalStatus.PENDING

    # Edit draft
    repo.update_draft_content(pid, "Edited Title", "Edited Description", "RFID, IoT", approved=True)
    updated = repo.draft_for(pid)
    assert updated["title"] == "Edited Title"
    assert updated["approval_status"] == ApprovalStatus.APPROVED
