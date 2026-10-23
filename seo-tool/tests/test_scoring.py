import pytest
from app import calculate_health_score


def test_clean_site():
    assert calculate_health_score({}, pages_crawled=10) == 100


def test_few_low_issues_minimal_impact():
    # 3 low issues on 10 pages should have negligible deduction
    score = calculate_health_score({"LOW": 3}, pages_crawled=10)
    assert score == 100


def test_excessive_low_issues_escalation():
    # 50 low issues on 10 pages should cross the threshold and escalate
    score_normal = calculate_health_score({"LOW": 10}, pages_crawled=10)
    score_excess = calculate_health_score({"LOW": 50}, pages_crawled=10)
    assert score_normal > score_excess
    # With 50 low issues, score drops into the 'Needs work' zone (< 80)
    assert score_excess < 80


def test_critical_issue_cap():
    # Even on 100 pages, a critical blocker caps the score at max 65
    score = calculate_health_score({"CRITICAL": 1}, pages_crawled=100)
    assert score == 65

    # Multiple critical issues drive it down further
    score_multi = calculate_health_score({"CRITICAL": 5}, pages_crawled=10)
    assert score_multi < 65


def test_medium_issues_moderate_impact():
    score = calculate_health_score({"MEDIUM": 5}, pages_crawled=10)
    # 5 medium issues on 10 pages shouldn't destroy the score
    assert 90 <= score <= 96


def test_zero_or_none_pages_handled_safely():
    assert calculate_health_score({"LOW": 2}, pages_crawled=0) == 99
    assert calculate_health_score({}, pages_crawled=None) == 100
