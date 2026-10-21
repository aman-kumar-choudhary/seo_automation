# seo-tool

Responsible, white-hat SEO + GEO auditing: polite crawling, a technical audit, AI-search (GEO) readiness
checks, prioritized recommendations, and a reviewed propose -> approve -> apply -> rollback flow for titles
and meta descriptions.

No tool can guarantee rankings, citations in AI answers, or that a search engine will never treat a site as spam.

## Install
    pip install -e ".[fast,google,dev]"     # add ,js and run `playwright install chromium` for JS rendering
    pytest

## Commands
    seo-tool audit https://example.com --max-pages 200 --keywords "trail running shoes"
    seo-tool audit https://example.com --exclude "/cart" --exclude "[?&]sort=" --max-query-params 3
    seo-tool audit https://example.com --max-pages 2000 --resume
    seo-tool audit https://example.com --pagespeed 10
    seo-tool audit https://example.com --gsc-property sc-domain:example.com --gsc-credentials sa.json
    SEO_AI_MODEL=<model> SEO_AI_API_KEY=... seo-tool audit https://example.com --ai --brand-voice "plain English"
    seo-tool review seo_output/<run>/proposals.json
    seo-tool apply seo_output/<run>/proposals.json --site-root ./public --base-url https://example.com   # dry run
    seo-tool apply ... --execute
    seo-tool rollback seo_output/<run>/backups/<timestamp>

Any setting can be set with SEO_<NAME> environment variables (e.g. SEO_MAX_PAGES=500).

## GEO (AI search) checks
- Search/AI-search crawler access in robots.txt (OAI-SearchBot, PerplexityBot, Claude-SearchBot, Bingbot)
- AI training crawler policy (GPTBot, ClaudeBot, Google-Extended) - informational only
- Snippet controls (nosnippet, max-snippet, data-nosnippet) that limit Google's AI features
- Structured data that doesn't match visible text
- Authorship/date signals on articles, entity markup on the home page, scannable structure
- llms.txt presence (reported only; unofficial proposal)

Crawler tokens live in seo_tool/bots.py. Review them periodically against each provider's documentation.
Google: AI Overviews and AI Mode have no extra technical requirements beyond normal SEO.

## Adding checks
Create a module in seo_tool/checks/, register a CheckSpec, decorate a function with @page_check or
@site_check, and import it in seo_tool/checks/__init__.py. External packages can use the
"seo_tool.checks" entry-point group instead.
