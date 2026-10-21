from __future__ import annotations

from .base import CheckSpec as C, Severity as S, issue, page_check, register

register(
    C("jsonld_invalid", "Invalid JSON-LD", "structured_data", S.HIGH, 3, 0.95,
      "Fix the JSON syntax and validate with Google's Rich Results Test.",
      "Unparseable structured data is ignored entirely."),
    C("jsonld_incomplete", "JSON-LD missing @context/@type", "structured_data", S.MEDIUM, 2, 0.8,
      "Include @context (https://schema.org) and @type for every entity.",
      "Without these, parsers cannot interpret the markup."),
    C("structured_data_none", "No structured data", "structured_data", S.INFO, 1, 0.4,
      "Where relevant, add schema.org markup that matches visible content (Organization, Article, Product...). "
      "Never mark up content users can't see, or fake reviews/ratings.",
      "Accurate structured data can enable rich results; misleading markup can trigger manual actions."),
)


@page_check
def check_structured_data(page, site):
    if not page.ok:
        return
    for err in page.json_ld_errors:
        yield issue("jsonld_invalid", page.url, f"Invalid JSON-LD: {err}")
    for obj in page.json_ld:
        if not isinstance(obj, dict):
            yield issue("jsonld_incomplete", page.url, "JSON-LD block is not an object")
            continue
        if "@context" not in obj:
            yield issue("jsonld_incomplete", page.url, "JSON-LD block missing @context")
        items = obj["@graph"] if isinstance(obj.get("@graph"), list) else [obj]
        for it in items:
            if isinstance(it, dict) and "@type" not in it:
                yield issue("jsonld_incomplete", page.url, "JSON-LD entity missing @type")
    if page.indexable and not page.json_ld and not page.has_microdata and not page.json_ld_errors:
        yield issue("structured_data_none", page.url, "No JSON-LD, microdata or RDFa found")
