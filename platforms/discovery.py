"""Platform discovery module with automated web search and curated directory."""
from __future__ import annotations

import re
from urllib.parse import urlparse, unquote
import httpx
from bs4 import BeautifulSoup

SEARCH_QUERIES = (
    "top social bookmarking sites technology SEO",
    "social bookmarking websites submit link RFID IoT",
    "free social bookmarking sites list high DA",
    "industrial IoT hardware technology publishing platforms",
)

# Comprehensive seed directory of reputable social bookmarking & content sharing platforms
SEED_CANDIDATES = [
    {
        "name": "Reddit",
        "domain": "reddit.com",
        "registration_url": "https://www.reddit.com/register/",
        "submission_url": "https://www.reddit.com/submit",
        "relevance": "Technology, RFID, IoT & supply chain subreddits (e.g. r/technology, r/rfid)",
        "terms_url": "https://www.redditinc.com/policies/content-policy",
        "registration_requirements": "Reddit account required",
        "link_attributes": "rel='nofollow' / user-generated content",
        "public_visibility": "Publicly indexed and visible",
        "posting_restrictions": "Follow subreddit guidelines; no spamming",
        "available": True,
    },
    {
        "name": "Dev.to",
        "domain": "dev.to",
        "registration_url": "https://dev.to/enter",
        "submission_url": "https://dev.to/new",
        "relevance": "Developer, hardware IoT, and technical RFID engineering articles",
        "terms_url": "https://dev.to/terms",
        "registration_requirements": "GitHub or Email account required",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly indexable",
        "posting_restrictions": "Must be technical and original",
        "available": True,
    },
    {
        "name": "Hacker News",
        "domain": "news.ycombinator.com",
        "registration_url": "https://news.ycombinator.com/login",
        "submission_url": "https://news.ycombinator.com/submit",
        "relevance": "Show HN and technical discussion on RFID & hardware innovations",
        "terms_url": "https://news.ycombinator.com/newsguidelines.html",
        "registration_requirements": "HN account required",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly indexable",
        "posting_restrictions": "Strict submission guidelines; must satisfy curiosity",
        "available": True,
    },
    {
        "name": "Medium",
        "domain": "medium.com",
        "registration_url": "https://medium.com/m/signin",
        "submission_url": "https://medium.com/new-story",
        "relevance": "Thought leadership and technology case studies on RFID systems",
        "terms_url": "https://policy.medium.com/medium-terms-of-service-9db0094a1e0f",
        "registration_requirements": "Medium account required",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly indexable",
        "posting_restrictions": "Original content; no deceptive backlinking",
        "available": True,
    },
    {
        "name": "LinkedIn",
        "domain": "linkedin.com",
        "registration_url": "https://www.linkedin.com/signup",
        "submission_url": "https://www.linkedin.com/feed/",
        "relevance": "B2B enterprise technology, asset tracking & RFID supply chain updates",
        "terms_url": "https://www.linkedin.com/legal/user-agreement",
        "registration_requirements": "Verified account",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly indexable based on post settings",
        "posting_restrictions": "Professional business content only",
        "available": True,
    },
    {
        "name": "Diigo",
        "domain": "diigo.com",
        "registration_url": "https://www.diigo.com/sign-up",
        "submission_url": "https://www.diigo.com/item/new/bookmark",
        "relevance": "Research and knowledge sharing for RFID & industrial automation",
        "terms_url": "https://www.diigo.com/terms",
        "registration_requirements": "Account required",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Public bookmarks indexable",
        "posting_restrictions": "Descriptive summaries and tags required",
        "available": True,
    },
    {
        "name": "Folkd",
        "domain": "folkd.com",
        "registration_url": "https://www.folkd.com/register",
        "submission_url": "https://www.folkd.com/submit",
        "relevance": "Social bookmarking community for tech and business websites",
        "terms_url": "https://www.folkd.com/page/terms",
        "registration_requirements": "Registration required",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly accessible bookmarks",
        "posting_restrictions": "Title and description must be accurate",
        "available": True,
    },
    {
        "name": "BizSugar",
        "domain": "bizsugar.com",
        "registration_url": "https://www.bizsugar.com/register",
        "submission_url": "https://www.bizsugar.com/submit",
        "relevance": "Small business and enterprise technology solutions sharing",
        "terms_url": "https://www.bizsugar.com/terms",
        "registration_requirements": "BizSugar community account",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly indexed",
        "posting_restrictions": "Relevant to business owners & technology implementers",
        "available": True,
    },
    {
        "name": "Slashdot",
        "domain": "slashdot.org",
        "registration_url": "https://slashdot.org/login.pl",
        "submission_url": "https://slashdot.org/submission",
        "relevance": "News for nerds; hardware, RFID telemetry & computing",
        "terms_url": "https://slashdot.org/terms.pl",
        "registration_requirements": "Slashdot account",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly indexable",
        "posting_restrictions": "Curated editorial review",
        "available": True,
    },
    {
        "name": "Scoop.it",
        "domain": "scoop.it",
        "registration_url": "https://www.scoop.it/signup",
        "submission_url": "https://www.scoop.it/curate",
        "relevance": "Content curation and social bookmarking network",
        "terms_url": "https://www.scoop.it/terms-of-use",
        "registration_requirements": "Account required",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Public curation topic indexable",
        "posting_restrictions": "Quality topic curation",
        "available": True,
    },
    {
        "name": "Pearltrees",
        "domain": "pearltrees.com",
        "registration_url": "https://www.pearltrees.com/join",
        "submission_url": "https://www.pearltrees.com/",
        "relevance": "Visual social bookmarking and collection curation",
        "terms_url": "https://www.pearltrees.com/terms",
        "registration_requirements": "Account required",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Public collections indexed",
        "posting_restrictions": "Appropriate collection categorization",
        "available": True,
    },
    {
        "name": "Digg",
        "domain": "digg.com",
        "registration_url": "https://digg.com/login",
        "submission_url": "https://digg.com/submit",
        "relevance": "Trending stories, tech links and web highlights",
        "terms_url": "https://digg.com/terms",
        "registration_requirements": "Digg profile",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly visible",
        "posting_restrictions": "No automated spamming",
        "available": True,
    },
    {
        "name": "Raindrop.io",
        "domain": "raindrop.io",
        "registration_url": "https://raindrop.io/app/#/signup",
        "submission_url": "https://raindrop.io/app/#/add",
        "relevance": "All-in-one bookmark manager with public sharing collections",
        "terms_url": "https://raindrop.io/terms",
        "registration_requirements": "Raindrop account",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Public collection indexable",
        "posting_restrictions": "Proper collection tags",
        "available": True,
    },
    {
        "name": "Hashnode",
        "domain": "hashnode.com",
        "registration_url": "https://hashnode.com/onboard",
        "submission_url": "https://hashnode.com/draft",
        "relevance": "Developer & engineering blogging community",
        "terms_url": "https://hashnode.com/terms",
        "registration_requirements": "Account required",
        "link_attributes": "rel='nofollow'",
        "public_visibility": "Publicly indexable",
        "posting_restrictions": "Technical content",
        "available": True,
    },
]


def normalize(item: dict) -> dict | None:
    """Normalizes and validates a candidate platform dictionary."""
    url = item.get("url") or item.get("submission_url") or item.get("registration_url")
    domain = (item.get("domain") or (urlparse(url).netloc.lower() if url else "")).strip().removeprefix("www.")
    if not domain or "." not in domain:
        return None

    # Filter out search engines, analytics, and CDNs from discovered candidates
    ignored = {"google.", "bing.", "yahoo.", "duckduckgo.", "yandex.", "baidu.", "cloudflare.", "amazon.", "w3.org"}
    if any(ig in domain for ig in ignored):
        return None

    base = f"https://{domain}"
    return {
        "name": item.get("name") or domain.split(".")[0].capitalize(),
        "domain": domain,
        "registration_url": item.get("registration_url") or base,
        "submission_url": item.get("submission_url") or url or base,
        "relevance": item.get("relevance") or "Discovered Social SEO Candidate",
        "terms_url": item.get("terms_url") or "",
        "registration_requirements": item.get("registration_requirements") or "Standard account required",
        "link_attributes": item.get("link_attributes") or "rel='nofollow' / user-generated content",
        "public_visibility": item.get("public_visibility") or "Publicly indexable",
        "posting_restrictions": item.get("posting_restrictions") or "Follow community terms; no spamming",
        "available": item.get("available", True),
    }


async def auto_search_social_bookmarking_sites(query: str, max_results: int = 15) -> list[dict]:
    """Actively searches the web for social bookmarking and SEO content sharing sites."""
    found = []
    # Query DuckDuckGo HTML endpoint without requiring paid API keys
    url = f"https://html.duckduckgo.com/html/?q={httpx.URL(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select("a.result__url") or soup.select(".result__snippet")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    # Extract redirect target
                    match = re.search(r"uddg=([^&]+)", href)
                    if match:
                        clean_url = unquote(match.group(1))
                    elif href.startswith("http"):
                        clean_url = href
                    else:
                        continue

                    netloc = urlparse(clean_url).netloc.lower().removeprefix("www.")
                    if netloc and "." in netloc and len(netloc) < 40:
                        found.append({
                            "name": netloc.split(".")[0].capitalize(),
                            "domain": netloc,
                            "url": f"https://{netloc}",
                            "submission_url": f"https://{netloc}",
                            "relevance": f"Web-discovered Social SEO site via query: '{query[:30]}...'",
                        })
                        if len(found) >= max_results:
                            break
    except Exception:
        pass

    return found


async def discover(repository, settings) -> int:
    """Discovers platforms from seed directory, search API, and live web auto-search."""
    candidates = list(SEED_CANDIDATES)

    # 1. External search API if configured
    if settings.search_api_url and settings.search_api_token:
        async with httpx.AsyncClient(timeout=15) as client:
            for query in SEARCH_QUERIES:
                try:
                    response = await client.get(
                        settings.search_api_url,
                        params={"q": query, "limit": settings.discovery_max_results},
                        headers={"Authorization": f"Bearer {settings.search_api_token}"},
                    )
                    if response.status_code == 200:
                        candidates.extend(response.json().get("results", []))
                except Exception:
                    pass

    # 2. Automated live web search if enabled
    if settings.auto_search_web:
        for query in SEARCH_QUERIES[:2]:
            web_results = await auto_search_social_bookmarking_sites(query, max_results=10)
            candidates.extend(web_results)

    # Deduplicate and upsert to database
    seen = set()
    added = 0
    for raw in candidates:
        item = normalize(raw)
        if item and item["domain"] not in seen:
            repository.upsert_platform(item)
            seen.add(item["domain"])
            added += 1

    return added
