# What This Project Actually Does

## Purpose

SEO & GEO Audit Suite is a **local, read-only website auditing tool**. You give
it a website URL and it crawls a limited portion of that website, checks for
SEO and AI-search-readiness issues, and produces reports with recommended
fixes.

It has two ways to use the same audit engine:

- A browser dashboard started with `./run_ui.sh`.
- A command-line tool started with `seo-tool audit <url>` from `seo-tool/`.

It is intended for sites you are authorized to audit. It does not bypass bot
protection, CAPTCHAs, or `robots.txt` restrictions.

## What Happens When You Run an Audit

1. The app normalizes the URL and creates an output folder under `seo_output/`.
2. It fetches and respects `robots.txt`, including any declared crawl delay.
3. It looks for sitemap URLs (from `robots.txt` or `/sitemap.xml`) and discovers
   same-site links from crawled pages.
4. It crawls only up to the selected page and depth limits. It ignores assets,
   skips excluded/crawl-trap URLs, and does not normally leave the target site.
5. It parses each reachable HTML page and records page data such as status code,
   final URL, title, meta description, headings, links, canonical tags, robots
   directives, images, schema, and social tags.
6. It runs page-level and site-level checks, groups the resulting issues, and
   ranks recommendations by severity, likely impact, confidence, and number of
   affected pages.
7. It writes the reports and (when appropriate) conservative metadata proposals.

The dashboard runs this work in a background thread and streams progress logs
to the browser. Completed reports remain on disk and appear in the dashboard's
history while the server is running.

## What the Dashboard Controls Do

| Control | Effect |
| --- | --- |
| Website URL | Starting page of the audit. `https://` is added if omitted. |
| Maximum pages | Hard cap on fetched HTML pages; it keeps audits bounded. |
| Maximum depth | How many same-site link levels are followed from the start page. |
| Crawl delay | Minimum pause between requests. The dashboard enforces at least 0.5 seconds; a larger `robots.txt` delay takes priority. |
| Render JavaScript | Uses Playwright/Chromium to render JavaScript-dependent pages. It must be installed separately. |
| Check external links | Checks outbound links too; otherwise link checking is more limited. |
| Keywords | Comma-separated focus terms used only when validating metadata proposals for repetition/stuffing risk. |

## What It Checks

The audit engine includes checks in these areas:

- **Indexing and crawlability:** HTTP errors, redirects, canonical/robots
  signals, robots access, sitemap coverage, and crawl completeness.
- **Metadata and content:** missing, duplicate, or overly long titles and meta
  descriptions; heading structure; thin or weakly structured content signals.
- **Links and images:** broken links, redirecting links, image alt text, and
  related page-quality issues.
- **Technical SEO:** performance signals, internationalization/hreflang,
  structured data, Open Graph/social metadata, and site-wide issues.
- **GEO / AI search readiness:** whether selected search and AI crawler tokens
  are allowed by `robots.txt`; restrictive snippet directives; visible-text vs.
  schema consistency; authorship/date/entity signals; scannable structure; and
  whether `llms.txt` is present.

GEO checks are diagnostic only. In particular, `llms.txt` is reported as an
unofficial signal, not a requirement. Passing these checks does **not**
guarantee inclusion in Google AI Overviews, ChatGPT search, Perplexity, Claude,
or any other AI answer.

## Results and Health Score

Every audit creates `seo_output/<host>-<timestamp>/` with these files:

| File | Use |
| --- | --- |
| `report.md` | Readable summary, issues, and recommendations. |
| `audit.json` | Full machine-readable audit data and configuration. |
| `issues.csv` | One row per detected issue. |
| `pages.csv` | Collected data for crawled pages. |
| `recommendations.csv` | Grouped, prioritized fixes. |
| `proposals.json` | Metadata changes awaiting human review. |
| `audit.log` | CLI logs when the command-line tool is used. |

The dashboard's health score uses a page-normalized multi-tier escalation model:

```text
Threshold = max(10, pages_crawled)
LowPenalty = (low × 0.5) if low <= Threshold else (Threshold × 0.5 + (low - Threshold) × 1.75)
RawDeductions = (critical × 30 + high × 12 + medium × 3 + LowPenalty)
NormalizedDeduction = RawDeductions / √(pages_crawled)
Health Score = round(100 - NormalizedDeduction), constrained to 0–100.
(If critical > 0, the score is capped at 65 to ensure broken sites cannot score 'Good').
```

- **Critical issues** have high weight (-30) and prevent a site with severe indexing/crawl blockers from being rated "Good".
- **Medium issues** have low weight (-3) so minor metadata gaps don't crash the score.
- **Low issues** have minimal impact (0.5 pts) until they cross a threshold, after which they escalate (1.75 pts each) to reflect compounding technical debt.
- **Page normalization** ($\sqrt{\text{pages}}$) ensures large site crawls are not penalized unfairly compared to small crawls.

## Metadata Proposals: What Can and Cannot Be Changed

An audit itself never changes the audited website.

The tool may propose only:

- A title for a page with no `<title>`, based on its existing H1.
- A shorter version of an overly long existing title.
- A meta description for a page that lacks one, based on its existing first
  substantial paragraph.

Proposals are discarded if they are empty, duplicate another value, contain
HTML, or show keyword-stuffing risk. They must be reviewed first. Applying them
is a separate CLI-only operation for a local static-site folder:

```bash
seo-tool review seo_output/<run>/proposals.json
seo-tool apply seo_output/<run>/proposals.json --site-root ./public --base-url https://example.com
seo-tool apply seo_output/<run>/proposals.json --site-root ./public --base-url https://example.com --execute
```

The first `apply` command is a preview. `--execute` writes approved changes,
creates a backup, and can later be reversed with `seo-tool rollback`. There is
no automatic publishing to a CMS and no automatic bulk content generation.

## Optional Features

- **JavaScript rendering:** requires `playwright` and a Chromium installation.
- **Google PageSpeed Insights:** can assess a configured number of pages.
- **Google Search Console:** can inspect configured URLs with service-account
  credentials.
- **AI-assisted suggestions:** requires an explicitly configured API key and
  model; outputs remain proposals requiring review.

## Important Limits

- The app uses heuristic checks; it cannot guarantee rankings, traffic,
  indexing, AI citations, or freedom from spam classification.
- A page may be absent because it is beyond the chosen limits, blocked by
  `robots.txt`, protected by a challenge page, unavailable, or dynamically
  generated without JavaScript rendering.
- The dashboard keeps active task state in memory, so restarting the server
  clears active-task details. Finished report files are preserved in
  `seo_output/`.
- The dashboard permits requests from any origin (`CORS: *`) and has no built-in
  authentication. Keep it bound to `127.0.0.1` unless you add access controls.

## Start It Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e "./seo-tool[fast,dev]"
./run_ui.sh
```

Then open `http://127.0.0.1:8765`. For all installation, configuration, CLI,
Docker, and development commands, see [README.md](README.md).
