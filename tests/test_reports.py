import pytest
import pandas as pd
from database.repository import Repository
from database.models import Status
from reports.report_generator import export, generate_summary


def test_export_generates_valid_csv(tmp_path):
    repo = Repository(tmp_path / "test.db")
    pid = repo.upsert_platform({
        "name": "ExportPlatform",
        "domain": "export.org",
        "submission_url": "https://export.org/submit",
    })
    repo.set_metrics(pid, {"da": 45, "pa": 30, "spam_score": 2, "provider": "Moz Authorized"}, Status.ELIGIBLE)
    repo.save_draft(pid, "RFID Innovions", "RFID details at https://innovions.org/", "https://innovions.org/", "RFID", True)
    repo.record_submission(pid, None, "https://innovions.org/", Status.PUBLISHED, published_url="https://export.org/p/123")

    csv_path = export(repo, output_dir=tmp_path / "output")
    assert csv_path.exists()

    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["platform_name"] == "ExportPlatform"
    assert df.iloc[0]["submission_status"] == Status.PUBLISHED
    assert df.iloc[0]["published_url"] == "https://export.org/p/123"


def test_generate_summary_statistics(tmp_path):
    repo = Repository(tmp_path / "test.db")
    pid1 = repo.upsert_platform({"name": "P1", "domain": "p1.org"})
    pid2 = repo.upsert_platform({"name": "P2", "domain": "p2.org"})
    repo.set_metrics(pid1, {}, Status.ELIGIBLE)
    repo.set_metrics(pid2, {}, Status.REJECTED, "Low DA")

    summary = generate_summary(repo)
    assert summary["total_platforms"] == 2
    assert summary["eligibility_breakdown"][Status.ELIGIBLE] == 1
    assert summary["eligibility_breakdown"][Status.REJECTED] == 1
