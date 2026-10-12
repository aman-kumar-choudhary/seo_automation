"""Multi-platform test server hosting N realistic Social Media SEO & bookmarking websites."""
from __future__ import annotations

import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Predefined templates for generating N distinct Social Media SEO platforms
PLATFORM_DEFINITIONS = [
    {
        "id": "tech-bookmarks",
        "name": "TechBookmarks SEO",
        "domain": "techbookmarks.org",
        "tagline": "Curated technology and hardware social bookmarking network",
        "da": 68.0,
        "pa": 52.0,
        "spam_score": 1.2,
        "theme": "#2563eb",
    },
    {
        "id": "rfid-pulse",
        "name": "RFID & IoT Pulse",
        "domain": "rfidpulse.net",
        "tagline": "Industrial IoT, RFID asset tracking & supply chain community",
        "da": 54.0,
        "pa": 41.0,
        "spam_score": 2.1,
        "theme": "#059669",
    },
    {
        "id": "dev-wire",
        "name": "DevWire Social",
        "domain": "devwire.io",
        "tagline": "Developer & engineering article sharing directory",
        "da": 61.0,
        "pa": 46.0,
        "spam_score": 1.8,
        "theme": "#7c3aed",
    },
    {
        "id": "enterprise-biz",
        "name": "EnterpriseBiz News",
        "domain": "enterprisebiznews.com",
        "tagline": "B2B enterprise technology, warehouse & logistics portal",
        "da": 49.0,
        "pa": 38.0,
        "spam_score": 2.4,
        "theme": "#d97706",
    },
    {
        "id": "social-pin",
        "name": "SocialPin SEO Directory",
        "domain": "socialpinseo.org",
        "tagline": "High-authority social link submission & bookmark index",
        "da": 58.0,
        "pa": 44.0,
        "spam_score": 1.5,
        "theme": "#dc2626",
    },
    {
        "id": "smart-logistics",
        "name": "Smart Logistics Review",
        "domain": "smartlogisticsreview.com",
        "tagline": "Automated supply chain, RFID tags & inventory intelligence",
        "da": 46.0,
        "pa": 36.0,
        "spam_score": 2.8,
        "theme": "#0891b2",
    },
    {
        "id": "iot-network",
        "name": "IoT Network Digest",
        "domain": "iotnetworkdigest.net",
        "tagline": "Wireless telemetry, RFID sensors and smart industry links",
        "da": 52.0,
        "pa": 39.0,
        "spam_score": 1.9,
        "theme": "#4f46e5",
    },
    {
        "id": "tech-spotlight",
        "name": "TechSpotlight Daily",
        "domain": "techspotlightdaily.org",
        "tagline": "Discover innovation in RFID, computing and enterprise software",
        "da": 64.0,
        "pa": 49.0,
        "spam_score": 1.1,
        "theme": "#0d9488",
    },
]


def create_platform_html(p: dict, host: str, port: int) -> str:
    sub_url = f"http://{host}:{port}/platform/{p['id']}/submit"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{p['name']} - Social Media Bookmarking & SEO</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0; padding: 0; background: #f1f5f9; color: #1e293b;
    }}
    header {{
      background: {p['theme']}; color: white; padding: 20px 40px;
      display: flex; justify-content: space-between; align-items: center;
    }}
    header h1 {{ margin: 0; font-size: 1.4rem; }}
    header p {{ margin: 4px 0 0; opacity: 0.9; font-size: 0.85rem; }}
    .container {{
      max-width: 800px; margin: 30px auto; background: white;
      padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }}
    .auth-badge {{
      display: inline-block; background: #e2e8f0; color: #334155;
      padding: 4px 10px; border-radius: 9999px; font-size: 0.8rem; font-weight: 600;
    }}
    .form-group {{ margin-bottom: 20px; }}
    label {{ display: block; font-weight: 600; margin-bottom: 6px; font-size: 0.9rem; }}
    input[type="text"], input[type="url"], textarea {{
      width: 100%; box-sizing: border-box; padding: 12px;
      border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem;
    }}
    textarea {{ min-height: 100px; resize: vertical; }}
    button {{
      background: {p['theme']}; color: white; border: none;
      padding: 12px 24px; font-size: 1rem; font-weight: 600;
      border-radius: 8px; cursor: pointer; transition: opacity 0.2s;
    }}
    button:hover {{ opacity: 0.9; }}
    .seo-info {{
      background: #f8fafc; border: 1px solid #e2e8f0;
      padding: 12px; border-radius: 8px; margin-bottom: 24px; font-size: 0.85rem; color: #64748b;
    }}
    .alert-success {{
      background: #dcfce7; color: #166534; padding: 16px; border-radius: 8px; margin-top: 20px;
      font-weight: 600; border: 1px solid #86efac;
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>🌐 {p['name']}</h1>
      <p>{p['tagline']}</p>
    </div>
    <div class="auth-badge">✓ Operator Session Verified</div>
  </header>
  <div class="container">
    <div class="seo-info">
      <strong>Platform Domain:</strong> {p['domain']} |
      <strong>Domain Authority:</strong> {p['da']} |
      <strong>Page Authority:</strong> {p['pa']} |
      <strong>Spam Score:</strong> {p['spam_score']}%
    </div>
    <h2>Submit New Social Bookmark / Link</h2>
    <form id="bookmark-form" action="{sub_url}" method="POST">
      <div class="form-group">
        <label for="url">Target Website URL *</label>
        <input type="url" id="url" name="url" placeholder="https://..." required />
      </div>
      <div class="form-group">
        <label for="title">Submission Title *</label>
        <input type="text" id="title" name="title" placeholder="Descriptive SEO title" required />
      </div>
      <div class="form-group">
        <label for="description">Article / Story Summary *</label>
        <textarea id="description" name="description" placeholder="Meaningful description including primary keyword..." required></textarea>
      </div>
      <div class="form-group">
        <label for="tags">Keywords / Tags</label>
        <input type="text" id="tags" name="tags" placeholder="e.g. RFID, technology, logistics" />
      </div>
      <button type="submit" id="submit-btn">Publish Social Bookmark</button>
    </form>
    <div id="result-box" style="display: none;"></div>
  </div>
</body>
</html>"""


def create_test_server(count: int = 5, host: str = "127.0.0.1", port: int = 8766) -> tuple[FastAPI, list[dict]]:
    app = FastAPI(title="Social Media SEO Multi-Platform Test Server")
    platforms = PLATFORM_DEFINITIONS[:count]

    @app.get("/")
    async def index():
        html = "<h1>Social Media SEO Platform Mock Hub</h1><ul>"
        for p in platforms:
            html += f"<li><a href='/platform/{p['id']}'>{p['name']} ({p['domain']})</a></li>"
        html += "</ul>"
        return HTMLResponse(html)

    for p in platforms:
        pid = p["id"]

        def make_routes(p_info=p):
            @app.get(f"/platform/{p_info['id']}", response_class=HTMLResponse)
            async def get_form():
                return HTMLResponse(create_platform_html(p_info, host, port))

            @app.post(f"/platform/{p_info['id']}/submit", response_class=HTMLResponse)
            async def post_form(request: Request):
                body = await request.body()
                from urllib.parse import parse_qs
                data = parse_qs(body.decode("utf-8", errors="ignore"))
                title = data.get("title", [""])[0]
                url = data.get("url", [""])[0]
                return HTMLResponse(f"""
                <!DOCTYPE html><html><body>
                <div class="alert-success" id="success-banner">
                  <h3>✓ Submission Successful!</h3>
                  <p>Your social bookmark for <strong>{title}</strong> ({url}) has been published and indexed.</p>
                  <p>Permalink: <a href="/platform/{p_info['id']}/post/1234">View Post</a></p>
                </div>
                </body></html>
                """)

        make_routes(p)

    @app.get("/metrics")
    async def get_metrics(domain: str):
        # Match domain to platform
        for p in platforms:
            if p["domain"].lower() == domain.lower():
                return {
                    "domain": domain,
                    "da": p["da"],
                    "pa": p["pa"],
                    "spam_score": p["spam_score"],
                    "provider": "Moz API Authorized Mock",
                }
        return JSONResponse(status_code=404, content={"error": "Domain not found"})

    return app, platforms
