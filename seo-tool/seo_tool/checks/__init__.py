import logging
from importlib.metadata import entry_points

from .base import PAGE_CHECKS, SITE_CHECKS, SPECS, CheckSpec, Issue, Severity, issue, page_check, register, site_check
from . import (content, external_signals, geo, headings, images, indexing, international, links,  # noqa: F401
               metadata, performance, site, social, structured_data)


def _load_plugins() -> None:
    """Third-party packages register checks via:
    [project.entry-points."seo_tool.checks"]
    mycheck = "my_package.my_module"
    """
    for ep in entry_points(group="seo_tool.checks"):
        try:
            ep.load()
        except Exception as exc:  # a broken plugin must not break the tool
            logging.getLogger("seo_tool.plugins").warning("failed to load plugin %s: %r", ep.name, exc)


_load_plugins()

__all__ = ["PAGE_CHECKS", "SITE_CHECKS", "SPECS", "CheckSpec", "Issue", "Severity",
           "issue", "page_check", "register", "site_check"]
