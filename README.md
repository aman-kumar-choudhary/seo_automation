# SEO & GEO Audit Suite

A local, white-hat website auditor with a browser dashboard and command-line interface. It crawls a site respectfully, identifies technical SEO, content, structured-data, and AI-search (GEO) issues, then produces prioritized recommendations and metadata proposals for review.

For a plain-language explanation of the audit workflow, the checks, its limits,
and exactly what it can change, read [DOCUMENTATION.md](DOCUMENTATION.md).

The tool is read-only while auditing. Metadata changes are only made through the CLI's explicit `apply --execute` flow, which creates backups first.

> Audit results are heuristic checks, not a guarantee of search ranking, AI citations, or spam classification. Only audit websites you are authorized to crawl and respect their `robots.txt` rules.

## Features

- Polite, same-site crawling with `robots.txt`, sitemap, crawl-delay, retry, throttling, and crawl-trap safeguards
- Technical checks for indexing, metadata, headings, links, images, performance signals, internationalization, social metadata, and structured data
- GEO/AI-search readiness checks, including AI crawler access, snippet controls, authorship/date/entity signals, and `llms.txt` reporting
- Prioritized issues and actionable recommendations
- Optional JavaScript rendering, Google PageSpeed Insights, Google Search Console inspection, and AI-assisted metadata suggestions
- Dashboard with live audit logs, report history, health score, export, and print support
- Reports in Markdown, JSON, and CSV formats
- Review, dry-run, apply, and rollback commands for generated title and meta-description proposals

## Project layout

```text
.
├── app.py                 # FastAPI dashboard and REST/SSE API
├── run_ui.sh              # Dashboard launcher
├── static/                # Dashboard HTML, CSS, and browser JavaScript
├── seo-tool/              # Installable CLI/audit engine package
│   ├── seo_tool/
│   ├── tests/
│   ├── seo.example.toml   # Example CLI configuration
│   └── Dockerfile         # CLI container image
└── seo_output/            # Generated at runtime; ignored by Git
```

## Requirements

- Python 3.11 or newer
- `pip`
- Internet access to crawl the target website

JavaScript rendering additionally requires Playwright and Chromium. Google integrations and AI suggestions require their respective credentials/API settings.

## Quick start: dashboard

Create and activate a virtual environment, then install the dashboard and audit-engine dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]"
pip install -e "./seo-tool[fast,dev]"
```

Start the dashboard:

```bash
./run_ui.sh
```

Open <http://127.0.0.1:8765>, enter a website URL, choose crawl limits/settings, and select **Run Audit**. Results are saved under `seo_output/<host>-<timestamp>/` and remain available in the dashboard history while the server is running.

To use JavaScript rendering:

```bash
pip install -e "./seo-tool[js]"
playwright install chromium
```

You can override the server address and port:

```bash
SEO_DASHBOARD_HOST=0.0.0.0 SEO_DASHBOARD_PORT=8000 ./run_ui.sh
```

## Command-line usage

Run CLI commands from the package directory after installation:

```bash
cd seo-tool
pip install -e ".[fast,google,dev]"

# Crawl a site and generate reports
seo-tool audit https://example.com --max-pages 200 --keywords "trail running shoes"

# Protect against crawl traps and skip irrelevant paths
seo-tool audit https://example.com --exclude "/cart" --exclude "[?&]sort=" --max-query-params 3

# Continue a limited or interrupted crawl
seo-tool audit https://example.com --max-pages 2000 --resume

# Run PageSpeed Insights against the top 10 indexable pages
seo-tool audit https://example.com --pagespeed 10
```

Metadata proposals are never applied automatically:

```bash
# Interactively review generated proposals
seo-tool review seo_output/<run>/proposals.json

# Preview static-site changes without writing files
seo-tool apply seo_output/<run>/proposals.json \
  --site-root ./public --base-url https://example.com

# Apply approved proposals (creates a backup first)
seo-tool apply seo_output/<run>/proposals.json \
  --site-root ./public --base-url https://example.com --execute

# Restore a backup if needed
seo-tool rollback seo_output/<run>/backups/<timestamp>
```

## Configuration

For CLI audits, copy and customize the supplied example:

```bash
cp seo-tool/seo.example.toml seo.toml
cd seo-tool
seo-tool audit https://example.com --config ../seo.toml
```

Configuration precedence is:

1. Built-in defaults
2. TOML configuration file
3. `SEO_*` environment variables
4. CLI options

For example:

```bash
SEO_MAX_PAGES=500 SEO_CRAWL_DELAY=2.0 seo-tool audit https://example.com
```

Useful optional integrations:

```bash
# Google Search Console (service-account credentials)
seo-tool audit https://example.com \
  --gsc-property sc-domain:example.com --gsc-credentials service-account.json

# AI metadata suggestions; proposals still require review
SEO_AI_MODEL=<model> SEO_AI_API_KEY=<key> \
  seo-tool audit https://example.com --ai --brand-voice "plain English"
```

Never commit API keys or service-account JSON credentials. Files ending in `.json.key` are ignored by default.

## Crawl safety

The crawler blocks localhost, private and link-local IP ranges, and known cloud-metadata endpoints before every request and redirect. This prevents a user-supplied URL from being used to probe internal services. For an isolated local test environment only, opt in explicitly with `--allow-private-networks` or `allow_private_networks = true` in the TOML configuration.

## Output files

Each audit creates a timestamped directory under `seo_output/` containing:

| File | Contents |
| --- | --- |
| `report.md` | Human-readable audit summary and prioritized recommendations |
| `audit.json` | Complete structured audit data and configuration |
| `issues.csv` | Individual detected issues |
| `pages.csv` | Crawled-page metrics and metadata |
| `recommendations.csv` | Aggregated, prioritized recommendations |
| `proposals.json` | Pending metadata proposals for review/apply |
| `audit.log` | CLI audit log (CLI runs) |

## API endpoints

The dashboard provides these local endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/audit` | Queue an audit |
| `GET /api/audit/status/{task_id}` | Get current task state |
| `GET /api/audit/stream/{task_id}` | Stream progress and logs with server-sent events |
| `GET /api/reports` | List saved reports |
| `GET /api/reports/{report_id}` | Fetch a report |
| `GET /api/reports/{report_id}/download/{file_name}` | Download an allowed report artifact |

## Development

The engine's test suite and checks run from `seo-tool/`:

```bash
cd seo-tool
pip install -e ".[fast,google,dev]"
ruff check .
pytest -q
mypy seo_tool
```

GitHub Actions runs linting and tests on Python 3.11 through 3.14; type checking is currently non-blocking.

## Docker (CLI)

Build from the `seo-tool` directory:

```bash
cd seo-tool
docker build -t seo-tool .
docker run --rm -v "$PWD/../seo_output:/work/seo_output" seo-tool \
  audit https://example.com --output-dir /work/seo_output
```

Pass `--build-arg WITH_JS=true` while building if JavaScript rendering is required.

## License

No license file is currently included. Add one before distributing or publishing this project.
