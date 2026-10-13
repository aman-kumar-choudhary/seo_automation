"""Tests for autonomous content quality scoring, relevance checking, and auto-approval."""
import pytest
from database.models import Draft
from content.evaluator import ContentEvaluator


def test_content_evaluator_high_quality_draft():
    evaluator = ContentEvaluator(primary_keyword="RFID", min_approval_score=75.0)

    draft = Draft(
        title="Industrial RFID Asset Tracking & Hardware Protocols",
        description="Innovions provides enterprise UHF RFID reader architectures and real-time inventory telemetry at https://innovions.org/. High accuracy data capture.",
        target_url="https://innovions.org/",
        tags="RFID, asset-tracking",
        valid=True,
    )

    result = evaluator.evaluate_draft(draft, "https://innovions.org/")
    assert result.composite_score >= 80.0
    assert result.grade in ("A+", "A")
    assert result.auto_approved is True
    assert "Autonomous auto-approval granted" in result.justification


def test_content_evaluator_missing_keyword_rejected():
    evaluator = ContentEvaluator(primary_keyword="RFID", min_approval_score=75.0)

    draft = Draft(
        title="General Web Development Discussion",
        description="Modern web frameworks and styling techniques at https://innovions.org/ without hardware mentions.",
        target_url="https://innovions.org/",
        tags="webdev",
        valid=True,
    )

    result = evaluator.evaluate_draft(draft, "https://innovions.org/")
    assert result.relevance_score < 60.0
    assert result.auto_approved is False
    assert result.grade in ("C", "F")


def test_content_evaluator_spam_penalty():
    evaluator = ContentEvaluator(primary_keyword="RFID", min_approval_score=75.0)

    draft = Draft(
        title="RFID Super Cheap! Click Here! Buy Now!",
        description="Buy now! 100% free guaranteed best discount RFID tags at https://innovions.org/! Act now!!!",
        target_url="https://innovions.org/",
        tags="deals",
        valid=True,
    )

    result = evaluator.evaluate_draft(draft, "https://innovions.org/")
    assert result.safety_score <= 50.0
    assert result.auto_approved is False
