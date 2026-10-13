# Innovions SEO Social Bookmarking Automation with Live Browser Monitoring

A modular, robust, and safe **SEO Social Bookmarking Automation System** built with **Python 3.12+**, **Playwright (Chromium)**, **FastAPI WebSockets**, and **SQLite** for **[Innovions](https://innovions.org/)** targeting the primary keyword **`RFID`**.

---

## 1. Key Capabilities

- **Mandatory Visible Browser Execution by Default**: Launches Chromium in headed mode with configurable `slow_mo` (default: 300ms) and automatic `$DISPLAY` verification. A headless mode is available only when explicitly requested (`--headless`).
- **Live Monitoring Dashboard**: Built using FastAPI and WebSockets, rendering real-time execution states, live progress counters, SEO metric cards, an interactive draft editor, timestamped activity logs, screenshot previews, and **Platform Quick-Add** without page refreshes.
- **Visual Browser Feedback**: Real-time DOM element highlighting (`outline: 3px solid #ff9900; box-shadow: ...`) before filling fields or clicking buttons, automatically restoring original element styles post-interaction.
- **Workflow Control Panel**: Real-time operator controls including **Start**, **Pause**, **Resume**, **Stop**, **Skip Platform**, **Approve Submission**, **Reject Submission**, **Auto-Loop (Never Stop)**, **Auto-Approve Toggle**, **Take Screenshot**, and **Open Current URL**.
- **Continuous Autonomous Auto-Task**: Never-stopping background loop that periodically searches the web for fresh bookmarking platforms, verifies domain authority metrics, generates unique drafts, and executes submissions.
- **Network Resilience & Domain Throttling**: Exponential backoff retry policies, dynamic user-agent rotation across realistic browser fingerprints, per-domain rate limiting, and circuit breakers preventing cascaded connection errors.
- **Automated Platform Health & Availability Monitor**: Pre-screens candidate platforms before launching browser automation to verify DNS, HTTP status, SSL certificate validity, and latency, safely skipping dead domains.
- **Organic SERP Ranking & Visibility Tracker**: Monitors search engine ranking positions for target keywords (`RFID`, `RFID Innovions`) and tracks rank movements in SQLite.
- **Webhook Alert Notifications**: Outbound webhook dispatcher supporting Slack, Discord, and generic JSON hooks for published bookmarks, manual intervention requests, and cycle summaries.
- **Semantic Keyword Clustering & LSI Engine**: 5 distinct semantic clusters (`Asset Tracking & Inventory`, `Industrial IoT & Smart Sensors`, `Supply Chain & Logistics Visibility`, `Hardware Protocols`, `Enterprise Software`) with intelligent LSI keyword injection and rotation strategies (`ROUND_ROBIN`, `RELEVANCE_WEIGHTED`, `RANDOM`).
- **Human-Like Physical Interaction Emulator**: Keystroke timing jitter (20–65ms), natural typo and Backspace correction simulation, smooth Bézier mouse curve movements, and incremental wheel scrolling.
- **Intelligent Form & Rich-Text Editor Detector**: Automatic DOM inspection discovering text inputs, textareas, contenteditable `div` containers (ProseMirror, Quill), category select dropdowns, and submission buttons.
- **Technical SEO Backlink Auditor**: Live auditing of published bookmark links verifying `dofollow` vs `nofollow` vs `ugc` link attributes, robots meta indexability (`noindex`), anchor text relevance (`RFID`), canonicalization, and TTFB latency, generating a 0–100 Backlink Quality Score.
- **Executive Reporting (HTML, CSV, JSON)**: Generates publication-ready executive HTML audit reports with styled KPI cards and data tables, comprehensive CSV records, and structured JSON files.
- **Platform Discovery & Genuine SEO Metric Validation**: Discovers candidate tech and bookmarking platforms; queries authorized metric providers (e.g., Moz API) or curated authority benchmarks for Domain Authority (DA >= 20), Page Authority (PA >= 15), and Spam Score (< 10%).

---

## 2. Project Architecture

```text
automation/
├── main.py                             # CLI entrypoint and server/browser orchestrator
├── hard_dry_test.py                    # Standalone multi-platform hard dry test script
├── config.py                           # Pydantic-based configuration and environment validation
├── requirements.txt                    # Project dependencies
├── .env.example                        # Environment variable configuration template
├── README.md                           # Documentation, architecture, and user guide
├── automation/
│   ├── browser.py                      # Headed VisibleBrowser with DOM highlighting, UA rotation & throttling
│   ├── controller.py                   # WorkflowController and interactive command dispatcher
│   ├── submission.py                   # 18-step Playwright submission workflow orchestrator
│   ├── network_resilience.py           # User-agent rotation, rate limiting, circuit breaker & backoff retry
│   ├── serp_tracker.py                 # Organic search engine ranking position monitor
│   ├── form_detector.py                # Intelligent multi-strategy DOM form & rich-text detector
│   ├── human_emulator.py               # Human typing jitter, typo simulation, and mouse curves
│   ├── seo_auditor.py                  # Live technical SEO backlink equity and indexability auditor
│   ├── verification.py                 # DOM and URL submission outcome verification
│   └── screenshots.py                  # Structured pre/post/error screenshot manager
├── dashboard/
│   ├── app.py                          # FastAPI web application, Quick-Add REST endpoint, and WebSocket event hub
│   ├── websocket.py                    # WebSocket hub exports
│   └── templates/
│       └── index.html                  # Live real-time dashboard UI with Quick-Add & SEO Equity
├── platforms/
│   ├── discovery.py                    # Active search engine web discovery & curated platforms
│   ├── metrics.py                      # SEO authority metrics provider (Moz API + benchmark engine)
│   ├── eligibility.py                  # Authority and spam score filtering logic (DA>=20, Spam<10%)
│   ├── health_checker.py               # Pre-screening platform availability and latency checker
│   ├── test_platforms_server.py        # Mock test server hosting N realistic bookmarking sites
│   └── adapters/
│       ├── base.py                     # BasePlatformAdapter abstract interface
│       └── supported_platforms.py      # Dedicated adapters (Reddit, Dev.to, HN, Demo, Generic)
├── content/
│   ├── generator.py                    # Content generator with keyword density validation
│   ├── keywords.py                     # Semantic keyword clustering & LSI keyword rotation
│   └── templates.py                    # Platform-tailored templates (technical, enterprise, community)
├── notifications/
│   └── notifier.py                     # Webhook alert dispatcher (Slack, Discord, JSON) & audit logging
├── database/
│   ├── models.py                       # Status StrEnums, Draft, and Submission data classes
│   ├── repository.py                   # SQLite repository with migrations, deduplication, audits & rankings
│   └── schema.sql                      # SQL database schema definitions (platforms, drafts, submissions, audits, serp, health)
├── reports/
│   └── report_generator.py             # Executive HTML, CSV, and JSON report generator
├── tests/                              # Pytest automated test suite (58 passing tests)
├── screenshots/                        # Diagnostic screenshot captures
├── traces/                             # Playwright session traces (session.zip)
└── output/                             # Exported CSV, HTML, and JSON analytical reports
```

---

## 3. Installation & Setup

### Prerequisites
- Python 3.12+ (tested on Python 3.12.14)
- Active graphical desktop display (`$DISPLAY` or `$WAYLAND_DISPLAY`) for visible browser mode

### Quickstart

```bash
# 1. Navigate to directory
cd /home/aman-/web_world/automation

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright Chromium binaries
playwright install chromium
```

---

## 4. CLI Usage

### Launch Visible Browser and Live Dashboard
```bash
# Default mode: launches headed Chromium window and live web dashboard
python main.py run
```
*Navigates to `https://innovions.org/` in visible Chromium, opens the live monitoring dashboard tab at `http://127.0.0.1:8765`, and initiates discovery and metric validation.*

### Continuous Auto-Pilot Mode (Never Stops)
```bash
# Fully autonomous: searches web, verifies authority, auto-approves, and never stops
python main.py auto --interval 30
```

### Execute a Safe Dry Run
```bash
# Populates form fields with DOM highlighting and captures screenshots, but withholds submission
python main.py run --dry-run
```

### Multi-Platform Hard Dry Test (N Websites)
```bash
# Automated end-to-end dry test across N distinct Social Media SEO platforms
python main.py hard-dry-test --count 5
```

### Export Executive SEO Reports
```bash
# Exports CSV, HTML, and JSON reports
python main.py report --format all
```

### Check Organic SERP Rankings
```bash
python main.py check-serp --keyword RFID
```

### Pre-Screen Candidate Platform Availability
```bash
python main.py check-health
```

### Test Outbound Webhook Notifications
```bash
python main.py test-notification --message "Innovions SEO automation ready"
```

### Audit Any URL's Backlink Attributes
```bash
python main.py audit --url https://example.com/bookmark/101 --target https://innovions.org/
```

---

## 5. Automated Testing Suite

Run the full automated test suite using `pytest`:

```bash
./.venv/bin/pytest -v
```

### Test Coverage (72 passing tests)
- `tests/test_account_manager.py`: Persistent session storage, credentials lookup, and automated login.
- `tests/test_captcha_solver.py`: Automated CAPTCHA detection, sitekey parsing, and token injection.
- `tests/test_content_evaluator.py`: Autonomous draft relevance, accuracy, readability scoring, and auto-approval.
- `tests/test_public_verifier.py`: Independent unauthenticated verification of public post reachability and links.
- `tests/test_utm_and_analytics.py`: Campaign UTM query building and referral traffic impact estimation.
- `tests/test_enhanced_audit.py`: Robots.txt crawl verification, canonical consistency, and indexability grades.
- `tests/test_browser_headed.py`: Headed Chromium defaults, slow_mo, DISPLAY checks, headless override.
- `tests/test_dashboard_websocket.py`: Dashboard rendering, command dispatch, draft updating, WebSocket state.
- `tests/test_dashboard_quick_add.py`: Platform Quick-Add REST endpoint and queueing.
- `tests/test_controls.py`: Controller Pause, Resume, Stop, Skip, Approve, and Reject checkpoints.
- `tests/test_content_and_generator.py`: Keyword density, URL integrity, anti-stuffing rules, templates.
- `tests/test_keywords.py`: Semantic keyword clusters, LSI keyword generation, and rotation strategies.
- `tests/test_human_emulator.py`: Keystroke timing jitter, typo simulations, and Bézier mouse clicks.
- `tests/test_form_detector.py`: Multi-strategy selector heuristics and automated form population.
- `tests/test_seo_auditor.py`: Backlink attribute auditing, dofollow/nofollow checks, and robots meta indexability.
- `tests/test_network_resilience.py`: User-agent rotation, rate limiting, circuit breaker, and retry policy.
- `tests/test_health_checker.py`: Pre-screening platform availability and batch checking.
- `tests/test_serp_tracker.py`: SERP results parsing and rank position identification.
- `tests/test_notifications.py`: Webhook notification delivery, mock simulation, and database audit logs.
- `tests/test_report_exports.py`: Executive HTML and JSON report generation.
- `tests/test_reports.py`: CSV generation and statistical summary calculations.
- `tests/test_hard_dry_test.py`: Full end-to-end multi-platform hard dry test execution.
- `tests/test_database_persistence.py`: Deduplication, retry counters, and workflow recovery.
- `tests/test_submission_and_dryrun.py`: Dry-run publication safeguards and screenshot management.
