from __future__ import annotations

from database.models import Status
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import Settings


def decision(metrics: dict | None, settings: Settings) -> tuple[Status, str | None]:
    """Evaluates platform eligibility against configured SEO authority and quality thresholds.
    
    Filters:
    - DA >= min_da (default 20)
    - PA >= min_pa (default 15) when available
    - Spam Score < max_spam_score (strictly below 10%)
    - Metrics must be present from an authorized provider (otherwise UNVERIFIED)
    """
    if not metrics:
        return Status.UNVERIFIED, "Required authorized SEO metrics are unavailable"

    da = metrics.get("da")
    pa = metrics.get("pa")
    spam_score = metrics.get("spam_score")

    if da is None or da < settings.min_da:
        return Status.REJECTED, f"DA {da} is below minimum requirement ({settings.min_da})"

    if pa is not None and pa < settings.min_pa:
        return Status.REJECTED, f"PA {pa} is below minimum requirement ({settings.min_pa})"

    if spam_score is None or spam_score >= settings.max_spam_score:
        return Status.REJECTED, f"Spam Score {spam_score}% is not strictly below {settings.max_spam_score}%"

    return Status.ELIGIBLE, None
