"""Tests for campaign UTM tracking and referral traffic analytics estimation."""
from content.utm import build_utm_url
from automation.traffic_analytics import TrafficAnalyticsTracker


def test_build_utm_url():
    url = build_utm_url(
        base_url="https://innovions.org/",
        domain="reddit.com",
        cluster_name="Asset Tracking & Inventory",
    )
    assert "https://innovions.org/" in url
    assert "utm_source=reddit.com" in url
    assert "utm_medium=social_bookmark" in url
    assert "utm_campaign=rfid_seo" in url
    assert "utm_content=asset-tracking-and-inventory" in url


def test_traffic_analytics_tracker():
    tracker = TrafficAnalyticsTracker(target_url="https://innovions.org/")

    res_high = tracker.estimate_platform_impact(
        domain="reddit.com",
        da=91.0,
        is_dofollow=True,
        quality_score=95,
        cluster_name="Industrial IoT",
    )
    assert "High Tier" in res_high.traffic_tier
    assert res_high.estimated_monthly_impressions > 1000
    assert res_high.equity_value_score > 100.0

    res_std = tracker.estimate_platform_impact(
        domain="nicheblog.org",
        da=25.0,
        is_dofollow=False,
        quality_score=60,
    )
    assert "Standard Tier" in res_std.traffic_tier
    assert res_std.estimated_monthly_impressions < 500

    summary = tracker.summarize_campaign([res_high.to_dict(), res_std.to_dict()])
    assert summary["total_campaign_assets"] == 2
    assert summary["total_estimated_monthly_impressions"] > 1000
    assert summary["total_domain_equity_value_usd"] > 100.0
