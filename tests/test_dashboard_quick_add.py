import pytest
from starlette.testclient import TestClient
from dashboard.app import EventHub, create_app


def test_dashboard_quick_add_endpoint(tmp_path):
    hub = EventHub()
    app = create_app(hub, screenshot_dir=tmp_path / "screenshots")
    client = TestClient(app)

    response = client.post("/platforms/add", json={"url": "https://quickaddtech.com/submit"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["domain"] == "quickaddtech.com"

    # Verify item queued in hub.platform_add_queue
    assert hub.platform_add_queue.qsize() == 1
    item = hub.platform_add_queue.get_nowait()
    assert item["domain"] == "quickaddtech.com"
    assert item["submission_url"] == "https://quickaddtech.com/submit"


def test_dashboard_quick_add_invalid_url(tmp_path):
    hub = EventHub()
    app = create_app(hub, screenshot_dir=tmp_path / "screenshots")
    client = TestClient(app)

    response = client.post("/platforms/add", json={"url": ""})
    assert response.status_code == 400
