"""Check registry. To add a check: create a module, register CheckSpecs, decorate a function
with @page_check (page, site) or @site_check (site) that yields issue(...), and import the module
in checks/__init__.py (or expose it via the "seo_tool.checks" entry point). The crawler never changes."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Callable, Iterable

if TYPE_CHECKING:
    from ..crawler import SiteData
    from ..parser import PageData


class Severity(IntEnum):
    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


@dataclass(frozen=True)
class CheckSpec:
    id: str
    title: str
    category: str
    severity: Severity
    impact: int          # expected SEO impact 1-5
    confidence: float    # how sure the heuristic is, 0-1
    recommendation: str
    why: str


@dataclass
class Issue:
    check_id: str
    url: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def spec(self) -> CheckSpec:
        return SPECS[self.check_id]


PageCheck = Callable[["PageData", "SiteData"], Iterable[Issue]]
SiteCheck = Callable[["SiteData"], Iterable[Issue]]
SPECS: dict[str, CheckSpec] = {}
PAGE_CHECKS: list[PageCheck] = []
SITE_CHECKS: list[SiteCheck] = []


def register(*specs: CheckSpec) -> None:
    for s in specs:
        if s.id in SPECS:
            raise ValueError(f"duplicate check id: {s.id}")
        if not (1 <= s.impact <= 5 and 0 < s.confidence <= 1):
            raise ValueError(f"invalid impact/confidence for {s.id}")
        SPECS[s.id] = s


def page_check(fn: PageCheck) -> PageCheck:
    PAGE_CHECKS.append(fn)
    return fn


def site_check(fn: SiteCheck) -> SiteCheck:
    SITE_CHECKS.append(fn)
    return fn


def issue(check_id: str, url: str, message: str, **evidence: Any) -> Issue:
    if check_id not in SPECS:
        raise KeyError(f"unregistered check id: {check_id}")
    return Issue(check_id, url, message, evidence)
