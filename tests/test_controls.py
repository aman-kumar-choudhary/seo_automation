import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from config import Settings
from database.repository import Repository
from database.models import Status, ApprovalStatus
from dashboard.app import EventHub
from automation.controller import WorkflowController


@pytest.mark.asyncio
async def test_controller_pause_resume_checkpoint(tmp_path):
    settings = Settings(database_path=tmp_path / "test.db")
    repo = Repository(settings.database_path)
    hub = EventHub()
    browser = MagicMock()
    browser.page = None

    controller = WorkflowController(settings, repo, hub, browser)
    assert not controller.paused
    assert not controller.stopped

    # Test pause
    await controller._process_command("pause")
    assert controller.paused is True

    # Checkpoint should block while paused until resumed
    async def resume_after_delay():
        await asyncio.sleep(0.1)
        await controller._process_command("resume")

    resume_task = asyncio.create_task(resume_after_delay())
    ok = await controller.checkpoint()
    await resume_task

    assert ok is True
    assert controller.paused is False


@pytest.mark.asyncio
async def test_controller_stop_checkpoint(tmp_path):
    settings = Settings(database_path=tmp_path / "test.db")
    repo = Repository(settings.database_path)
    hub = EventHub()
    browser = MagicMock()

    controller = WorkflowController(settings, repo, hub, browser)
    await controller._process_command("stop")
    assert controller.stopped is True

    # Checkpoint should return False when stopped
    ok = await controller.checkpoint()
    assert ok is False


@pytest.mark.asyncio
async def test_controller_skip_flag(tmp_path):
    settings = Settings(database_path=tmp_path / "test.db")
    repo = Repository(settings.database_path)
    hub = EventHub()
    browser = MagicMock()

    controller = WorkflowController(settings, repo, hub, browser)
    assert not controller.skip

    await controller._process_command("skip")
    assert controller.skip is True


@pytest.mark.asyncio
async def test_controller_approve_and_reject(tmp_path):
    settings = Settings(database_path=tmp_path / "test.db")
    repo = Repository(settings.database_path)
    hub = EventHub()
    browser = MagicMock()

    pid = repo.upsert_platform({"name": "TestPlatform", "domain": "testplatform.org"})
    repo.save_draft(pid, "Title", "Desc", settings.target_url, "tags", True)

    controller = WorkflowController(settings, repo, hub, browser)
    controller.current_platform_id = pid

    # Approve
    await controller.approve(True)
    draft = repo.draft_for(pid)
    assert draft["approval_status"] == ApprovalStatus.APPROVED

    # Reject
    await controller.approve(False)
    draft = repo.draft_for(pid)
    assert draft["approval_status"] == ApprovalStatus.REJECTED
