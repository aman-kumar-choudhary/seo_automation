"""Webhook and external alert notification dispatcher (Slack, Discord, generic JSON)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import httpx

if TYPE_CHECKING:
    from database.repository import Repository
    from config import Settings

logger = logging.getLogger(__name__)


@dataclass
class NotificationPayload:
    event_type: str
    title: str
    message: str
    platform_name: str | None = None
    target_url: str = "https://innovions.org/"
    published_url: str | None = None
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class WebhookNotifier:
    """Sends real-time event notifications to configured webhooks with audit logging."""

    def __init__(self, settings: Settings, repo: Repository | None = None):
        self.settings = settings
        self.repo = repo
        self.webhook_url = settings.webhook_url
        self.enabled = settings.webhook_enabled and bool(self.webhook_url)

    async def notify(
        self,
        event_type: str,
        title: str,
        message: str,
        platform_name: str | None = None,
        published_url: str | None = None,
    ) -> bool:
        """Sends notification payload to configured webhook and records in database."""
        ts = datetime.now(timezone.utc).isoformat()
        payload = NotificationPayload(
            event_type=event_type,
            title=title,
            message=message,
            platform_name=platform_name,
            target_url=self.settings.target_url,
            published_url=published_url,
            timestamp=ts,
        )

        status_str = "SKIPPED_NOT_CONFIGURED"
        if self.enabled and self.webhook_url:
            try:
                # Format payload to be compatible with Slack, Discord, and generic JSON hooks
                json_body = {
                    "text": f"*{title}*\n{message}",
                    "event": event_type,
                    "platform": platform_name,
                    "target_url": self.settings.target_url,
                    "published_url": published_url,
                    "timestamp": ts,
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(self.webhook_url, json=json_body)
                    status_str = "DELIVERED" if resp.is_success else f"HTTP_{resp.status_code}"
            except Exception as exc:
                logger.warning("Failed to send webhook notification: %s", exc)
                status_str = f"ERROR: {exc}"
        else:
            status_str = "MOCK_SIMULATED"

        if self.repo and hasattr(self.repo, "record_notification"):
            self.repo.record_notification(
                event_type=event_type,
                channel="webhook",
                message=f"{title}: {message}",
                payload=payload.to_dict(),
                status=status_str,
            )

        return status_str in ("DELIVERED", "MOCK_SIMULATED")

    async def notify_published(self, platform_name: str, published_url: str) -> bool:
        return await self.notify(
            event_type="SUBMISSION_PUBLISHED",
            title=f"🚀 Bookmark Published: {platform_name}",
            message=f"Live backlink verified for Innovions (RFID) at {published_url}",
            platform_name=platform_name,
            published_url=published_url,
        )

    async def notify_intervention(self, platform_name: str, issue: str) -> bool:
        return await self.notify(
            event_type="MANUAL_INTERVENTION_REQUIRED",
            title=f"⚠️ Intervention Required: {platform_name}",
            message=f"Operator assistance needed in visible browser window: {issue}",
            platform_name=platform_name,
        )

    async def notify_cycle_completed(self, cycle_num: int, published_count: int) -> bool:
        return await self.notify(
            event_type="CYCLE_COMPLETED",
            title=f"🔁 Auto-Task Cycle #{cycle_num} Complete",
            message=f"Cycle finished with {published_count} total successful bookmark submissions.",
        )
