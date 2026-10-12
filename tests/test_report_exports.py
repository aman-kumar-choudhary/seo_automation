import json
import pytest
from database.repository import Repository
from database.models import Status
from reports.report_generator import export_html, export_json
from automation.seo_auditor import BacklinkAuditResult


def test_export_html_generates_valid_report(tmp_path):
    repo = Repository(tmp_path / "test.db")
    pid = repo.upsert_platform({
        "name": "AuditPlatform",
        "domain": "auditplatform.org",
        "submission_url": "https://auditplatform.org/submit",
    })
    repo.set_metrics(pid, {"da": 55, "pa": 40, "spam_score": 1, "provider": "Moz Authorized"}, Status.ELIGIBLE)
    repo.save_draft(pid, "RFID Tracking - Innovions", "Check RFID at https://innovions.org/", "https://innovions.org/", "RFID", True)
    repo.record_submission(pid, None, "https://innovions.org/", Status.PUBLISHED, published_url="https://auditplatform.org/post/100")

    audit = BacklinkAuditResult(
        published_url="https://auditplatform.org/post/100",
        target_url="https://innovions.org/",
        link_found=True,
        is_dofollow=True,
        quality_score=95,
    )
    repo.save_backlink_audit(pid, audit)

    html_file = export_html(repo, output_dir=tmp_path / "output")
    assert html_file.exists()

    content = html_file.read_text(encoding="utf-8")
    assert "Innovions SEO Automation Executive Report" in content
    assert "auditplatform.org" in content
    assert "https://innovions.org/" in content
    assert "PUBLISHED" in content


def test_export_json_generates_valid_document(tmp_path):
    repo = Repository(tmp_path / "test.db")
    pid = repo.upsert_platform({
        "name": "JsonPlatform",
        "domain": "jsonplatform.com",
    })
    repo.set_metrics(pid, {"da": 30, "pa": 20, "spam_score": 3}, Status.ELIGIBLE)

    json_file = export_json(repo, output_dir=tmp_path / "output")
    assert json_file.exists()

    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert "summary" in data
    assert "platforms" in data
    assert data["platforms_count"] == 1
    assert data["platforms"][0]["domain"] == "jsonplatform.com"
