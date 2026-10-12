import pytest
from starlette.testclient import TestClient
from dashboard.app import EventHub, create_app, DraftUpdateRequest


def test_dashboard_index_html(tmp_path):
    hub = EventHub()
    app = create_app(hub, screenshot_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Innovions SEO" in response.text
    assert "Workflow Controls" in response.text


def test_dashboard_commands_dispatch(tmp_path):
    hub = EventHub()
    app = create_app(hub, screenshot_dir=tmp_path)
    client = TestClient(app)

    # Valid commands
    for cmd in ["start", "pause", "resume", "stop", "skip", "approve", "reject", "screenshot", "open"]:
        resp = client.post(f"/command/{cmd}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert hub.commands.get_nowait() == cmd

    # Invalid command
    bad_resp = client.post("/command/unknown_cmd")
    assert bad_resp.status_code == 400


def test_dashboard_draft_update(tmp_path):
    hub = EventHub()
    app = create_app(hub, screenshot_dir=tmp_path)
    client = TestClient(app)

    payload = {
        "platform_id": 1,
        "title": "RFID Tracking Solutions by Innovions",
        "description": "Comprehensive RFID review at https://innovions.org/",
        "tags": "RFID, tech",
        "approve": True,
    }
    resp = client.post("/draft/update", json=payload)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    update_req = hub.draft_updates.get_nowait()
    assert update_req.platform_id == 1
    assert update_req.title == payload["title"]
    assert update_req.approve is True


def test_dashboard_websocket_snapshot(tmp_path):
    hub = EventHub()
    hub.state["operation"]["current_platform_name"] = "Reddit"
    app = create_app(hub, screenshot_dir=tmp_path)
    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data["event"] == "snapshot"
        assert data["data"]["operation"]["current_platform_name"] == "Reddit"
