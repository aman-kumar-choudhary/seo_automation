from __future__ import annotations

from ..urls import in_scope
from .base import CheckSpec as C, Severity as S, issue, page_check, register

UNVERIFIABLE = {401, 403, 429, 999}  # usually bot protection, not broken
GENERIC_ANCHORS = {"click here", "here", "read more", "more", "learn more", "this", "link", "this page"}

register(
    C("broken_internal_link", "Broken internal link", "links", S.HIGH, 4, 0.95,
      "Update the link to the correct URL or remove it.",
      "Broken links hurt users and waste crawl budget."),
    C("broken_external_link", "Broken external link", "links", S.MEDIUM, 2, 0.75,
      "Replace with a working, relevant source or remove the link.",
      "Dead outbound links degrade user experience and perceived quality."),
    C("internal_link_to_redirect", "Internal link points to a redirect", "links", S.LOW, 2, 0.9,
      "Link directly to the final URL.", "Avoids extra hops for users and crawlers."),
    C("redirect_chain", "Redirect chain", "links", S.MEDIUM, 2, 0.9,
      "Redirect straight to the final URL in a single hop.",
      "Chains slow users down and crawlers may stop following them."),
    C("redirect_temporary", "Temporary redirect on internal URL", "links", S.INFO, 1, 0.5,
      "Use 301/308 if the move is permanent; keep 302/307 only for genuinely temporary moves.",
      "Permanent redirects consolidate signals to the target more reliably."),
    C("empty_anchor", "Links without accessible text", "links", S.LOW, 1, 0.8,
      "Give links visible text, or alt text / aria-label for image/icon links.",
      "Anchor text helps users and search engines understand the destination."),
    C("generic_anchor", "Generic anchor text", "links", S.LOW, 1, 0.5,
      "Use natural, descriptive anchors ('pricing plans', not 'click here'). Don't force exact-match keywords.",
      "Descriptive anchors improve usability and context; over-optimised anchors look manipulative."),
    C("nofollow_internal", "Internal links marked nofollow", "links", S.INFO, 1, 0.6,
      "Remove rel=nofollow from internal links unless there is a specific reason.",
      "Nofollow on internal links can hinder discovery of your own pages."),
)


def _broken(status: int | None) -> bool:
    return status is not None and status >= 400 and status not in UNVERIFIABLE


@page_check
def check_links(page, site):
    if not page.ok or not page.links:
        return
    seen: set[str] = set()
    redirecting, empty, generic, nofollow = [], [], [], []
    for link in page.links:
        if not link.text:
            empty.append(link.url)
        elif link.text.lower().strip(" .!?»›→") in GENERIC_ANCHORS:
            generic.append(f"'{link.text}' -> {link.url}")
        if link.url in seen:
            continue
        seen.add(link.url)
        if in_scope(link.url, site.root_host, site.config.include_subdomains):
            if "nofollow" in link.rel:
                nofollow.append(link.url)
            target, redirects = site.lookup(link.url)
            if target is not None:
                if target.status and target.status >= 400 and not target.bot_challenge:
                    yield issue("broken_internal_link", page.url, f"Links to {link.url} (HTTP {target.status})",
                                target=link.url, status=target.status, anchor=link.text)
                elif redirects:
                    redirecting.append({"url": link.url, "to": target.final_url})
            elif link.url in site.link_status and _broken(site.link_status[link.url].status):
                st = site.link_status[link.url]
                yield issue("broken_internal_link", page.url, f"Links to {link.url} (HTTP {st.status})",
                            target=link.url, status=st.status, anchor=link.text)
        else:
            st = site.link_status.get(link.url)
            if st and (_broken(st.status) or (st.status is None and st.error and not st.blocked)):
                yield issue("broken_external_link", page.url, f"Links to {link.url} ({st.status or st.error})",
                            target=link.url, status=st.status, error=st.error)
    if redirecting:
        yield issue("internal_link_to_redirect", page.url, f"{len(redirecting)} link(s) to redirecting URLs",
                    links=redirecting[:20])
    if empty:
        yield issue("empty_anchor", page.url, f"{len(empty)} link(s) without accessible text", links=empty[:20])
    if generic:
        yield issue("generic_anchor", page.url, f"{len(generic)} generic anchor(s)", examples=generic[:10])
    if nofollow:
        yield issue("nofollow_internal", page.url, f"{len(nofollow)} internal nofollow link(s)",
                    links=nofollow[:20])


@page_check
def check_redirects(page, site):
    chain = page.redirect_chain
    if len(chain) > 1:
        yield issue("redirect_chain", page.url, f"{len(chain)} hops before {page.final_url}",
                    chain=[f"{status} {url}" for url, status in chain] + [f"{page.status} {page.final_url}"])
    if chain and any(status in (302, 307) for _, status in chain):
        yield issue("redirect_temporary", page.url, "Temporary redirect(s) in chain",
                    chain=[f"{status} {url}" for url, status in chain])
