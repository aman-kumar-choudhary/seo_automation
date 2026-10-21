import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

# Ensure seo-tool package is importable
BASE_DIR = Path(__file__).resolve().parent
SEO_TOOL_DIR = BASE_DIR / "seo-tool"
if str(SEO_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(SEO_TOOL_DIR))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from seo_tool.audit import run_audit
from seo_tool.changes import generate_proposals, save_proposals
from seo_tool.config import Config
from seo_tool.crawler import Crawler
from seo_tool.report import write_all
from seo_tool.state import CrawlState
from seo_tool.urls import normalize_url

OUTPUT_DIR = BASE_DIR / "seo_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SEO & GEO Audit Suite", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

# Global in-memory storage for running audit tasks
tasks: Dict[str, Dict[str, Any]] = {}


class AuditRequest(BaseModel):
    url: str
    max_pages: Optional[int] = 10
    max_depth: Optional[int] = 3
    crawl_delay: Optional[float] = 0.5
    render_js: Optional[bool] = False
    check_external: Optional[bool] = False
    keywords: Optional[str] = ""


class TaskLogHandler(logging.Handler):
    """Captures crawler and audit logs into the task's in-memory log list."""
    def __init__(self, task_id: str, logs_list: List[Dict[str, Any]]):
        super().__init__()
        self.task_id = task_id
        self.logs_list = logs_list

    def emit(self, record: logging.LogRecord):
        try:
            msg = record.getMessage()
            ctx = getattr(record, "ctx", {}) or {}
            self.logs_list.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": record.levelname,
                "msg": msg,
                "ctx": ctx,
            })
        except Exception:
            pass


def calculate_health_score(issues_by_severity: Dict[str, int]) -> int:
    """Calculates an intuitive 0-100 overall health score based on issues."""
    critical = issues_by_severity.get("CRITICAL", 0)
    high = issues_by_severity.get("HIGH", 0)
    medium = issues_by_severity.get("MEDIUM", 0)
    low = issues_by_severity.get("LOW", 0)

    score = 100 - (critical * 20 + high * 10 + medium * 3 + low * 1)
    return max(0, min(100, score))


def run_audit_worker(task_id: str, req_data: Dict[str, Any]):
    task = tasks[task_id]
    logs = task["logs"]
    raw_url = req_data.get("url", "").strip()

    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    parsed = urlsplit(raw_url)
    host = parsed.hostname or "site"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = OUTPUT_DIR / f"{host}-{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    task["status"] = "running"
    task["progress"] = "Initializing crawler & configurations..."
    task["target_url"] = raw_url
    task["started_at"] = datetime.now().isoformat()

    keywords_list = [k.strip() for k in req_data.get("keywords", "").split(",") if k.strip()]

    cfg = Config.load(None, {
        "max_pages": req_data.get("max_pages", 10),
        "max_depth": req_data.get("max_depth", 3),
        "crawl_delay": max(0.2, float(req_data.get("crawl_delay", 0.5))),
        "render_js": bool(req_data.get("render_js", False)),
        "check_external_links": bool(req_data.get("check_external", False)),
        "target_keywords": keywords_list,
        "output_dir": str(OUTPUT_DIR),
        "log_level": "INFO",
    })

    seo_logger = logging.getLogger("seo_tool")
    log_handler = TaskLogHandler(task_id, logs)
    seo_logger.addHandler(log_handler)

    try:
        task["progress"] = f"Checking robots.txt & crawling {raw_url}..."
        state_file = OUTPUT_DIR / f"{host}.crawlstate.sqlite"
        state = CrawlState(state_file)
        start_norm = normalize_url(raw_url, strip_tracking=cfg.strip_tracking_params) or raw_url
        state.clear(start_norm)

        crawler = Crawler(cfg)
        try:
            site = crawler.crawl(raw_url, state=state)
        finally:
            crawler.fetcher.close()
            state.close()

        task["progress"] = "Analyzing SEO, GEO, content & structured data..."
        audit = run_audit(site)

        task["progress"] = "Generating metadata proposals & compiling reports..."
        proposals = generate_proposals(site, audit.issues, cfg.target_keywords)
        save_proposals(run_dir / "proposals.json", proposals)
        write_all(run_dir, site, audit, proposals)

        # Load complete audit.json
        audit_json_path = run_dir / "audit.json"
        with open(audit_json_path, "r", encoding="utf-8") as f:
            audit_data = json.load(f)

        # Also load report.md
        report_md_path = run_dir / "report.md"
        report_md = report_md_path.read_text(encoding="utf-8") if report_md_path.exists() else ""

        # Compute health score
        health_score = calculate_health_score(audit_data.get("summary", {}).get("issues_by_severity", {}))
        audit_data["health_score"] = health_score
        audit_data["markdown_report"] = report_md
        audit_data["report_id"] = run_dir.name

        task["status"] = "completed"
        task["progress"] = "Audit completed successfully!"
        task["finished_at"] = datetime.now().isoformat()
        task["report_id"] = run_dir.name
        task["data"] = audit_data

    except Exception as exc:
        task["status"] = "error"
        task["error"] = str(exc)
        task["progress"] = f"Audit failed: {str(exc)}"
        logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": "ERROR",
            "msg": f"Audit error: {str(exc)}",
            "ctx": {},
        })
    finally:
        seo_logger.removeHandler(log_handler)


@app.post("/api/audit")
async def start_audit(req: AuditRequest):
    raw_url = req.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"
    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": "Queued for audit...",
        "target_url": raw_url,
        "logs": [],
        "created_at": datetime.now().isoformat(),
        "report_id": None,
        "data": None,
        "error": None,
    }

    executor.submit(run_audit_worker, task_id, req.dict())
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/audit/status/{task_id}")
async def get_audit_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]


@app.get("/api/audit/stream/{task_id}")
async def stream_audit_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        last_log_idx = 0
        while True:
            task = tasks.get(task_id)
            if not task:
                break

            current_logs = task["logs"][last_log_idx:]
            last_log_idx = len(task["logs"])

            payload = {
                "status": task["status"],
                "progress": task["progress"],
                "report_id": task.get("report_id"),
                "error": task.get("error"),
                "new_logs": current_logs,
            }
            if task["status"] in ("completed", "error"):
                if task["status"] == "completed":
                    payload["data"] = task.get("data")
                yield f"data: {json.dumps(payload)}\n\n"
                break

            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.7)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/reports")
async def list_reports():
    """Lists existing audit reports from the output directory."""
    reports = []
    if not OUTPUT_DIR.exists():
        return {"reports": []}

    for folder in sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        audit_file = folder / "audit.json"
        if not audit_file.exists():
            continue

        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            summary = data.get("summary", {})
            issues_sev = summary.get("issues_by_severity", {})
            health_score = calculate_health_score(issues_sev)
            reports.append({
                "report_id": folder.name,
                "start_url": summary.get("start_url", ""),
                "generated_at": data.get("generated_at", ""),
                "pages_crawled": summary.get("pages_crawled", 0),
                "total_issues": summary.get("total_issues", 0),
                "issues_by_severity": issues_sev,
                "duration_seconds": summary.get("duration_seconds", 0),
                "health_score": health_score,
            })
        except Exception:
            continue

    return {"reports": reports}


@app.get("/api/reports/{report_id}")
async def get_report_detail(report_id: str):
    folder = OUTPUT_DIR / report_id
    audit_file = folder / "audit.json"
    if not folder.is_dir() or not audit_file.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    with open(audit_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    report_md_file = folder / "report.md"
    if report_md_file.exists():
        data["markdown_report"] = report_md_file.read_text(encoding="utf-8")

    issues_sev = data.get("summary", {}).get("issues_by_severity", {})
    data["health_score"] = calculate_health_score(issues_sev)
    data["report_id"] = report_id
    return data


@app.get("/api/reports/{report_id}/download/{file_name}")
async def download_report_file(report_id: str, file_name: str):
    allowed_files = {"report.md", "audit.json", "issues.csv", "pages.csv", "recommendations.csv", "proposals.json"}
    if file_name not in allowed_files:
        raise HTTPException(status_code=400, detail="Invalid file requested")

    target = OUTPUT_DIR / report_id / file_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="File does not exist")

    media_types = {
        "md": "text/markdown",
        "json": "application/json",
        "csv": "text/csv",
    }
    ext = file_name.split(".")[-1]
    return FileResponse(target, media_type=media_types.get(ext, "application/octet-stream"), filename=file_name)


# Mount static assets directory
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>UI index.html not found</h2>", status_code=500)


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("SEO_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("SEO_DASHBOARD_PORT", os.environ.get("PORT", "8765")))
    print(f"\n=======================================================")
    print(f"🚀 SEO & GEO Audit Suite is starting at: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
