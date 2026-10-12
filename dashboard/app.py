from __future__ import annotations

import asyncio
import os
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel


class DraftUpdateRequest(BaseModel):
    platform_id: int | None = None
    title: str
    description: str
    tags: str = ""
    approve: bool = False


class PlatformAddRequest(BaseModel):
    url: str
    name: str | None = None


class EventHub:
    """Central event pub-sub hub connecting browser, controller, and web dashboard."""

    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.state: dict = {
            "operation": {
                "current_platform_name": "-",
                "current_website_url": "-",
                "workflow_stage": "INITIALIZING",
                "browser_action": "System starting",
                "current_submission_title": "-",
                "target_url": "https://innovions.org/",
                "eligibility_status": "-",
            },
            "progress": {
                "total_platforms_discovered": 0,
                "platforms_evaluated": 0,
                "platforms_rejected": 0,
                "platforms_eligible": 0,
                "submissions_completed": 0,
                "submissions_awaiting_approval": 0,
                "failed_submissions": 0,
                "overall_progress_percentage": 0,
            },
            "metrics": {
                "DA": None,
                "PA": None,
                "Spam Score": None,
                "Metric provider": None,
                "Eligibility": None,
                "Reason": None,
            },
            "draft": None,
            "intervention": None,
            "last_screenshot": None,
            "logs": [],
        }
        self.commands: asyncio.Queue[str] = asyncio.Queue()
        self.draft_updates: asyncio.Queue[DraftUpdateRequest] = asyncio.Queue()
        self.platform_add_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def add_platform(self, item: dict):
        await self.platform_add_queue.put(item)

    async def emit(self, event: str, data: dict | str | None):
        """Emits an event to all connected WebSocket clients and updates state."""
        if event == "state" and isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict) and isinstance(self.state.get(k), dict):
                    self.state[k].update(v)
                else:
                    self.state[k] = v
        elif event == "log" and isinstance(data, dict):
            self.state["logs"] = (self.state["logs"] + [data])[-200:]
        elif event == "intervention":
            self.state["intervention"] = data

        message = {"event": event, "data": data}
        for ws in list(self.clients):
            try:
                await ws.send_json(message)
            except Exception:
                self.clients.discard(ws)

    async def command(self, name: str):
        await self.commands.put(name)

    async def update_draft(self, req: DraftUpdateRequest):
        await self.draft_updates.put(req)


TEMPLATE_FILE = Path(__file__).parent / "templates" / "index.html"


def create_app(hub: EventHub, screenshot_dir: Path | str = "screenshots") -> FastAPI:
    """Builds FastAPI web application for the live monitoring dashboard."""
    app = FastAPI(title="Innovions SEO Automation Monitor")
    screenshots_path = Path(screenshot_dir).resolve()
    screenshots_path.mkdir(parents=True, exist_ok=True)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        if TEMPLATE_FILE.exists():
            return HTMLResponse(TEMPLATE_FILE.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Innovions SEO Monitor</h1>")

    @app.post("/command/{name}")
    async def handle_command(name: str):
        valid = {
            "start", "pause", "resume", "stop", "skip",
            "approve", "reject", "screenshot", "open",
            "toggle_continuous", "toggle_auto_approval"
        }
        if name not in valid:
            raise HTTPException(status_code=400, detail="Unknown command")
        await hub.command(name)
        return {"ok": True, "command": name}

    @app.post("/draft/update")
    async def update_draft(req: DraftUpdateRequest):
        await hub.update_draft(req)
        return {"ok": True}

    @app.post("/platforms/add")
    async def add_platform_api(req: PlatformAddRequest):
        from urllib.parse import urlparse
        from datetime import datetime
        raw_url = req.url.strip()
        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raw_url = f"https://{raw_url}"
        parsed = urlparse(raw_url)
        domain = (parsed.netloc or parsed.path).lower().strip().removeprefix("www.")
        if not domain or "." not in domain:
            raise HTTPException(status_code=400, detail="Invalid platform URL or domain")
        item = {
            "name": req.name or domain.title(),
            "domain": domain,
            "submission_url": raw_url,
            "registration_url": f"https://{domain}/register",
            "relevance": "technology, rfid, business bookmarking",
        }
        await hub.add_platform(item)
        await hub.emit(
            "log",
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"Quick-Add: Enqueued platform candidate '{domain}' for live evaluation.",
            },
        )
        return {"ok": True, "domain": domain}

    @app.get("/screenshots/{filename}")
    async def get_screenshot(filename: str):
        # Sanitize filename
        safe_name = Path(filename).name
        target = screenshots_path / safe_name
        if not target.exists():
            raise HTTPException(status_code=404, detail="Screenshot not found")
        return FileResponse(str(target), media_type="image/png")

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        hub.clients.add(ws)
        # Send current full state snapshot on connection
        await ws.send_json({"event": "snapshot", "data": hub.state})
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            hub.clients.discard(ws)

    return app
