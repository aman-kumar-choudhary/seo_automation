from __future__ import annotations

from .base import CheckSpec as C, Severity as S, issue, page_check, register

REQUIRED_OG = ("og:title", "og:description", "og:image", "og:url")

register(
    C("og_missing", "Missing Open Graph tags", "social", S.LOW, 1, 0.7,
      "Add og:title, og:description, og:image and og:url reflecting the page content.",
      "Controls how pages appear when shared; not a direct ranking factor."),
    C("og_image_relative", "Relative og:image URL", "social", S.LOW, 1, 0.8,
      "Use an absolute https URL for og:image.", "Many platforms ignore relative image URLs."),
)


@page_check
def check_open_graph(page, site):
    if not page.indexable:
        return
    missing = [p for p in REQUIRED_OG if not page.open_graph.get(p)]
    if missing:
        yield issue("og_missing", page.url, f"Missing: {', '.join(missing)}", missing=missing,
                    twitter_card=page.twitter.get("twitter:card"))
    img = page.open_graph.get("og:image")
    if img and not img.startswith(("http://", "https://")):
        yield issue("og_image_relative", page.url, f"og:image is relative: {img}")
