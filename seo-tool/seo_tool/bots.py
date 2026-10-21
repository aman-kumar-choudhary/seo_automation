"""Crawler tokens relevant to search and AI search (GEO). Review periodically: providers add and rename bots.
User-triggered fetchers (ChatGPT-User, Perplexity-User, Claude-User) are not listed because their operators
say robots.txt may not apply to user-initiated requests."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bot:
    token: str
    operator: str
    purpose: str
    category: str  # "search" (surfaces/cites pages) | "training" (model training)
    docs: str = ""


AI_BOTS: tuple[Bot, ...] = (
    Bot("Googlebot", "Google", "Google Search, including AI Overviews and AI Mode", "search",
        "https://developers.google.com/search/docs/appearance/ai-features"),
    Bot("Bingbot", "Microsoft", "Bing search", "search"),
    Bot("OAI-SearchBot", "OpenAI", "ChatGPT search results", "search", "https://developers.openai.com/api/docs/bots"),
    Bot("PerplexityBot", "Perplexity", "Perplexity search results", "search",
        "https://docs.perplexity.ai/docs/resources/perplexity-crawlers"),
    Bot("Claude-SearchBot", "Anthropic", "Claude search results", "search"),
    Bot("GPTBot", "OpenAI", "training generative AI models", "training",
        "https://developers.openai.com/api/docs/bots"),
    Bot("ClaudeBot", "Anthropic", "training generative AI models", "training"),
    Bot("Google-Extended", "Google", "AI training and grounding in some other Google systems (not Search)",
        "training", "https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers"),
)


def bot_access(robots, url: str) -> dict[str, bool]:
    """robots: a protego.Protego instance."""
    return {b.token: bool(robots.can_fetch(url, b.token)) for b in AI_BOTS}
