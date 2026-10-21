from __future__ import annotations

from .base import CheckSpec as C, Severity as S, issue, page_check, register

register(
    C("img_alt_missing", "Images without alt attribute", "images", S.LOW, 2, 0.85,
      "Add concise alt text describing informative images; use alt=\"\" for purely decorative ones. "
      "Don't stuff keywords into alt text.",
      "Alt text improves accessibility and helps image search understand images."),
    C("img_dimensions_missing", "Images without width/height", "performance", S.INFO, 1, 0.5,
      "Set width/height (or CSS aspect-ratio) to reserve space.",
      "Reduces layout shift (CLS), a Core Web Vitals metric."),
)


@page_check
def check_images(page, site):
    if not page.ok or not page.images:
        return
    missing = [i.src for i in page.images if i.alt is None]
    if missing:
        yield issue("img_alt_missing", page.url, f"{len(missing)} of {len(page.images)} images lack alt",
                    images=missing[:20])
    nodim = [i.src for i in page.images if not i.has_dimensions]
    if nodim:
        yield issue("img_dimensions_missing", page.url, f"{len(nodim)} image(s) without dimensions",
                    images=nodim[:20])
