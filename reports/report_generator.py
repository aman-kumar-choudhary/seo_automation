"""Execution, submission, and technical SEO backlink report generator (CSV, HTML, JSON)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def export(repository, output_dir: Path | str = "output") -> Path:
    """Exports structured execution and submission records to CSV."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    csv_file = out_path / "execution_report.csv"

    rows = repository.report_rows()
    data = [dict(row) for row in rows]
    df = pd.DataFrame(data)

    if df.empty:
        df = pd.DataFrame(
            columns=[
                "platform_id",
                "platform_name",
                "domain",
                "submission_url",
                "da",
                "pa",
                "spam_score",
                "metric_provider",
                "metrics_verified_at",
                "eligibility_status",
                "rejection_reason",
                "link_attributes",
                "public_visibility",
                "draft_title",
                "draft_description",
                "target_url",
                "approval_status",
                "submission_status",
                "published_url",
                "error_message",
                "screenshot_path",
                "submitted_at",
            ]
        )

    df.to_csv(csv_file, index=False)
    return csv_file


def generate_summary(repository) -> dict:
    """Computes a statistical breakdown of workflow execution results."""
    rows = repository.report_rows()
    total = len(rows)
    eligibility_counts: dict[str, int] = {}
    submission_counts: dict[str, int] = {}

    for r in rows:
        e_stat = r["eligibility_status"] or "UNKNOWN"
        eligibility_counts[e_stat] = eligibility_counts.get(e_stat, 0) + 1

        s_stat = r["submission_status"] or "NOT_SUBMITTED"
        submission_counts[s_stat] = submission_counts.get(s_stat, 0) + 1

    audit_summary = {}
    if hasattr(repository, "get_audit_summary"):
        audit_summary = repository.get_audit_summary()

    return {
        "total_platforms": total,
        "eligibility_breakdown": eligibility_counts,
        "submission_breakdown": submission_counts,
        "backlink_audits": audit_summary,
    }


def export_json(repository, output_dir: Path | str = "output") -> Path:
    """Exports all platform records and audit summaries to structured JSON."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    json_file = out_path / "execution_report.json"

    rows = repository.report_rows()
    data = [dict(row) for row in rows]
    summary = generate_summary(repository)

    audits = []
    if hasattr(repository, "get_backlink_audits"):
        audits = [dict(a) for a in repository.get_backlink_audits()]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "platforms_count": len(data),
        "platforms": data,
        "backlink_audits": audits,
    }

    json_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return json_file


def export_html(
    repository,
    output_dir: Path | str = "output",
    target_url: str = "https://innovions.org/",
    primary_keyword: str = "RFID",
) -> Path:
    """Generates an executive, publication-ready HTML audit report with visual cards and data tables."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    html_file = out_path / "seo_audit_report.html"

    rows = [dict(r) for r in repository.report_rows()]
    summary = generate_summary(repository)
    audit_summary = summary.get("backlink_audits", {})

    total_platforms = len(rows)
    published_count = sum(1 for r in rows if r.get("submission_status") == "PUBLISHED")
    eligible_count = sum(1 for r in rows if r.get("eligibility_status") in ("ELIGIBLE", "PUBLISHED"))
    avg_da = round(
        sum(float(r["da"]) for r in rows if r.get("da") is not None) / max(1, sum(1 for r in rows if r.get("da") is not None)),
        1
    ) if rows else 0.0

    dofollow_ratio = audit_summary.get("dofollow_ratio", 0.0)
    avg_quality = audit_summary.get("avg_quality_score", 0.0)

    # Build table rows
    table_rows_html = []
    for r in rows:
        domain = r.get("domain", "")
        name = r.get("platform_name", domain)
        da = r.get("da") if r.get("da") is not None else "—"
        pa = r.get("pa") if r.get("pa") is not None else "—"
        spam = f"{r.get('spam_score')}%" if r.get("spam_score") is not None else "—"
        e_stat = r.get("eligibility_status", "UNKNOWN")
        s_stat = r.get("submission_status") or "NOT_SUBMITTED"
        pub_url = r.get("published_url") or ""
        screenshot = r.get("screenshot_path") or ""

        e_badge_color = "#10b981" if e_stat in ("ELIGIBLE", "PUBLISHED") else ("#ef4444" if e_stat == "REJECTED" else "#f59e0b")
        s_badge_color = "#10b981" if s_stat == "PUBLISHED" else ("#3b82f6" if s_stat == "AWAITING_APPROVAL" else "#6b7280")

        pub_cell = f'<a href="{pub_url}" target="_blank" class="link">{pub_url[:35]}...</a>' if pub_url else '<span class="text-muted">None</span>'
        shot_cell = f'<a href="{screenshot}" target="_blank" class="btn-sm">View Shot</a>' if screenshot else '<span class="text-muted">—</span>'

        table_rows_html.append(f"""
        <tr>
            <td><strong>{name}</strong><br><small class="text-muted">{domain}</small></td>
            <td><span class="metric-val">{da}</span> / <small>{pa}</small></td>
            <td><span class="spam-val">{spam}</span></td>
            <td><span class="badge" style="background:{e_badge_color}22; color:{e_badge_color}; border:1px solid {e_badge_color}">{e_stat}</span></td>
            <td><span class="badge" style="background:{s_badge_color}22; color:{s_badge_color}; border:1px solid {s_badge_color}">{s_stat}</span></td>
            <td>{pub_cell}</td>
            <td>{shot_cell}</td>
        </tr>
        """)

    table_body = "\n".join(table_rows_html) or '<tr><td colspan="7" class="text-center">No platform submissions recorded yet.</td></tr>'

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Innovions SEO Social Bookmarking Audit Report</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.15);
            --border: #334155;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            padding: 32px 24px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 24px;
            margin-bottom: 32px;
        }}
        .brand h1 {{ font-size: 26px; font-weight: 700; color: #fff; }}
        .brand p {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
        .header-meta {{ text-align: right; font-size: 13px; color: var(--text-muted); }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }}
        .card-title {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px; }}
        .card-value {{ font-size: 32px; font-weight: 700; color: var(--accent); }}
        .card-sub {{ font-size: 12px; color: var(--text-muted); margin-top: 4px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            font-size: 14px;
        }}
        th, td {{ padding: 14px 18px; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{ background: #162032; font-weight: 600; color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
        tr:hover {{ background: rgba(255, 255, 255, 0.02); }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 600;
        }}
        .link {{ color: var(--accent); text-decoration: none; }}
        .link:hover {{ text-decoration: underline; }}
        .btn-sm {{
            display: inline-block;
            padding: 4px 10px;
            background: #2563eb;
            color: #fff;
            border-radius: 6px;
            text-decoration: none;
            font-size: 11px;
            font-weight: 500;
        }}
        .metric-val {{ font-weight: 600; color: #fff; }}
        .spam-val {{ color: #10b981; font-weight: 600; }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand">
                <h1>Innovions SEO Automation Executive Report</h1>
                <p>Automated Social Bookmarking & Technical Backlink Discovery</p>
            </div>
            <div class="header-meta">
                <div>Target URL: <strong>{target_url}</strong></div>
                <div>Primary Keyword: <strong>{primary_keyword}</strong></div>
                <div>Report Date: <strong>{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</strong></div>
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <div class="card-title">Platforms Evaluated</div>
                <div class="card-value">{total_platforms}</div>
                <div class="card-sub">{eligible_count} Passed Authority Filters</div>
            </div>
            <div class="card">
                <div class="card-title">Completed Submissions</div>
                <div class="card-value" style="color:var(--success)">{published_count}</div>
                <div class="card-sub">Published Live on Web</div>
            </div>
            <div class="card">
                <div class="card-title">Average Platform DA</div>
                <div class="card-value">{avg_da}</div>
                <div class="card-sub">Minimum DA Filter: 20</div>
            </div>
            <div class="card">
                <div class="card-title">Backlink Quality Score</div>
                <div class="card-value">{avg_quality}<small style="font-size:18px">/100</small></div>
                <div class="card-sub">Dofollow Ratio: {dofollow_ratio}%</div>
            </div>
        </div>

        <h2 style="font-size:18px; margin-bottom:16px; font-weight:600">Platform Submissions & Verification Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Platform & Domain</th>
                    <th>Authority (DA/PA)</th>
                    <th>Spam Score</th>
                    <th>Eligibility</th>
                    <th>Status</th>
                    <th>Published Referral Link</th>
                    <th>Audit Screenshot</th>
                </tr>
            </thead>
            <tbody>
                {table_body}
            </tbody>
        </table>

        <div class="footer">
            Generated autonomously by Innovions Playwright Automation System &bull; https://innovions.org/
        </div>
    </div>
</body>
</html>"""

    html_file.write_text(html_content, encoding="utf-8")
    return html_file
