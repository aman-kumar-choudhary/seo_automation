import pytest
from config import Settings
from database.repository import Repository
from notifications.notifier import WebhookNotifier


@pytest.mark.asyncio
async def test_webhook_notifier_simulated_mode(tmp_path):
    settings = Settings(webhook_enabled=False)
    repo = Repository(tmp_path / "test.db")
    notifier = WebhookNotifier(settings, repo)

    # In simulated mode, returns True and records log in database
    ok = await notifier.notify_published("TechBookmarks", "https://techbookmarks.org/p/42")
    assert ok is True

    logs = repo.get_notification_logs()
    assert len(logs) == 1
    assert logs[0]["event_type"] == "SUBMISSION_PUBLISHED"
    assert logs[0]["status"] == "MOCK_SIMULATED"
    assert "TechBookmarks" in logs[0]["message"]


@pytest.mark.asyncio
async def test_webhook_notifier_intervention(tmp_path):
    settings = Settings(webhook_enabled=False)
    repo = Repository(tmp_path / "test.db")
    notifier = WebhookNotifier(settings, repo)

    ok = await notifier.notify_intervention("Reddit", "CAPTCHA detected on page")
    assert ok is True

    logs = repo.get_notification_logs()
    assert len(logs) == 1
    assert logs[0]["event_type"] == "MANUAL_INTERVENTION_REQUIRED"
    assert "CAPTCHA" in logs[0]["message"]
