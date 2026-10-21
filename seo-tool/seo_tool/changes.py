"""Safe change management: conservative proposals -> validation -> human review -> dry-run diff ->
backup -> atomic apply -> change log -> rollback. Only titles and meta descriptions are supported,
and rule-based proposals reuse the page's own wording; there is no bulk content generation."""
from __future__ import annotations

import difflib
import hashlib
import html
import json
import logging
import os
import re
import shutil
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from .logging_setup import log
from .urls import bare_host

logger = logging.getLogger("seo_tool.changes")
TITLE_MAX, DESC_MAX = 60, 155
_SENT = re.compile(r"(?<=[.!?。！？])\s*")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Proposal:
    id: str
    url: str
    field: str            # "title" | "meta_description"
    before: str | None
    after: str
    reason: str
    check_id: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    status: str = "pending"   # pending | approved | rejected | applied | rolled_back
    history: list[dict[str, Any]] = field(default_factory=list)

    def set_status(self, status: str, note: str = "") -> None:
        self.history.append({"at": _now(), "from": self.status, "to": status, "note": note})
        self.status = status


# ---------- proposal generation ----------
def trim_at_word(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit + 1]
    if " " not in cut:  # scripts without spaces: hard cut
        return cut[:limit]
    return cut.rsplit(" ", 1)[0].rstrip(" ,;:-–—|")


def extract_summary(text: str, limit: int) -> str:
    out = ""
    for sentence in _SENT.split(" ".join(text.split())):
        if not sentence:
            continue
        candidate = f"{out} {sentence}".strip()
        if len(candidate) > limit:
            break
        out = candidate
    return out or trim_at_word(text, limit - 1) + "…"


def validate(after: str, before: str | None, field_name: str, in_use: set[str],
             keywords: list[str]) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings). Errors block the proposal."""
    errors, warnings = [], []
    text = " ".join(after.split())
    limit = TITLE_MAX if field_name == "title" else DESC_MAX + 5
    if not text:
        errors.append("empty value")
    if re.search(r"<[^>]+>", text):
        errors.append("contains HTML markup")
    if len(text) > limit:
        warnings.append(f"longer than {limit} characters")
    if text.lower() in in_use and text.lower() != (before or "").strip().lower():
        errors.append("duplicates another page's value")
    lowered = text.lower()
    for kw in keywords:
        n = len(re.findall(r"\b" + re.escape(kw.lower()) + r"\b", lowered))
        if n > 1:
            errors.append(f"keyword '{kw}' repeated {n} times (stuffing risk)")
    words = re.findall(r"\w{4,}", lowered)
    if words and max(Counter(words).values()) > 2:
        warnings.append("a word repeats more than twice")
    return errors, warnings


def generate_proposals(site, issues, keywords: list[str]) -> list[Proposal]:
    flagged = {(i.url, i.check_id) for i in issues}
    in_use = {
        "title": {(p.title or "").strip().lower() for p in site.pages.values() if p.indexable and p.title},
        "meta_description": {(p.meta_description or "").strip().lower()
                             for p in site.pages.values() if p.indexable and p.meta_description},
    }
    proposals: list[Proposal] = []

    def make(page, fname: str, after: str, check_id: str, confidence: float, reason: str) -> None:
        before = getattr(page, fname)
        errors, warnings = validate(after, before, fname, in_use[fname], keywords)
        if errors:
            log(logger, logging.INFO, "proposal discarded by safety checks", url=page.url, field=fname,
                errors=errors)
            return
        in_use[fname].add(after.lower())
        proposals.append(Proposal(hashlib.sha1(f"{page.url}|{fname}".encode()).hexdigest()[:12],
                                  page.url, fname, before, after, reason, check_id, confidence, warnings))

    for p in site.pages.values():
        if not p.indexable:
            continue
        if (p.url, "title_missing") in flagged and p.h1s and p.h1s[0]:
            make(p, "title", trim_at_word(p.h1s[0], TITLE_MAX), "title_missing", 0.7,
                 "The page has no <title>. Its main heading already describes the content in the site's own "
                 "words, so it is reused instead of writing new copy.")
        elif (p.url, "title_too_long") in flagged and p.title:
            after = trim_at_word(p.title, TITLE_MAX)
            if after and after != p.title:
                make(p, "title", after, "title_too_long", 0.4,
                     f"The title is {len(p.title)} characters and will likely be truncated. This is a mechanical "
                     "trim at a word boundary: check that the meaning survives, or rewrite it by hand.")
        if (p.url, "meta_description_missing") in flagged and p.first_paragraph:
            make(p, "meta_description", extract_summary(p.first_paragraph, DESC_MAX), "meta_description_missing",
                 0.6, "There is no meta description. The proposed text is taken word for word from the page's "
                 "first substantial paragraph to keep its meaning and voice. Edit it so it reads as a summary.")
    return proposals


def save_proposals(path: Path, proposals: list[Proposal]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps([asdict(p) for p in proposals], indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load_proposals(path: Path) -> list[Proposal]:
    return [Proposal(**d) for d in json.loads(path.read_text(encoding="utf-8"))]


def diff_text(before: str | None, after: str, label: str) -> str:
    return "\n".join(difflib.unified_diff([before or ""], [after], f"{label} (current)",
                                          f"{label} (proposed)", lineterm=""))


# ---------- interactive review ----------
def review(path: Path, keywords: list[str], input_fn: Callable[[str], str] = input,
           print_fn: Callable[..., None] = print) -> None:
    proposals = load_proposals(path)
    pending = [p for p in proposals if p.status == "pending"]
    if not pending:
        print_fn("No pending proposals.")
        return
    for n, p in enumerate(pending, 1):
        in_use = {o.after.lower() for o in proposals if o is not p and o.field == p.field and o.status != "rejected"}
        print_fn(f"\n[{n}/{len(pending)}] {p.url}\nField: {p.field} | check: {p.check_id} | "
                 f"confidence: {p.confidence:.0%}")
        print_fn(f"Why: {p.reason}")
        for w in p.warnings:
            print_fn(f"WARNING: {w}")
        print_fn(diff_text(p.before, p.after, p.field))
        while True:
            choice = input_fn("[a]pprove [r]eject [e]dit [s]kip [q]uit > ").strip().lower()
            if choice == "a":
                p.set_status("approved", "approved in review")
                break
            if choice == "r":
                p.set_status("rejected", input_fn("Reason (optional): ").strip())
                break
            if choice == "e":
                new = input_fn("New value: ").strip()
                errors, warnings = validate(new, p.before, p.field, in_use, keywords)
                if errors:
                    print_fn("Edit rejected: " + "; ".join(errors))
                    continue
                p.history.append({"at": _now(), "edited_from": p.after})
                p.after, p.warnings = new, warnings
                print_fn(diff_text(p.before, p.after, p.field))
                continue
            if choice == "s":
                break
            if choice == "q":
                save_proposals(path, proposals)
                return
        save_proposals(path, proposals)  # save after every decision
    print_fn("Review complete.")


# ---------- applying to a static site ----------
class ConflictError(Exception):
    pass


class StaticSiteAdapter:
    """Maps URLs to HTML files in a local static-site directory. A CMS adapter (WordPress REST,
    Shopify...) would implement the same `path_for` / read / write contract."""

    def __init__(self, root: str | Path, base_url: str) -> None:
        self.root = Path(root).resolve()
        self.base = urlsplit(base_url)

    def path_for(self, url: str) -> Path | None:
        u = urlsplit(url)
        if bare_host(u.hostname or "") != bare_host(self.base.hostname or ""):
            return None
        rel = unquote(u.path).lstrip("/")
        prefix = self.base.path.strip("/")
        if prefix and rel.startswith(prefix):
            rel = rel[len(prefix):].lstrip("/")
        candidates = [rel + "index.html"] if rel == "" or rel.endswith("/") else [rel, rel + ".html",
                                                                                   rel + "/index.html"]
        for c in candidates:
            path = (self.root / c).resolve()
            if not path.is_relative_to(self.root):  # path traversal guard
                return None
            if path.is_file() and path.suffix.lower() in (".html", ".htm"):
                return path
        return None


_TITLE_RE = re.compile(r"(<title\b[^>]*>)(.*?)(</title\s*>)", re.I | re.S)
_DESC_RE = re.compile(r"<meta\b(?=[^>]*\bname\s*=\s*[\"']?description(?=[\s\"'/>]))[^>]*>", re.I)
_CONTENT_RE = re.compile(r"(\bcontent\s*=\s*)(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_HEAD_RE = re.compile(r"<head\b[^>]*>", re.I)


def _norm(s: str | None) -> str:
    return " ".join(html.unescape(s or "").split())


def _ensure_same(current: str | None, before: str | None) -> None:
    if _norm(current) != _norm(before):
        raise ConflictError(f"file value {current!r} differs from audited value {before!r}; re-run the audit")


def _insert_in_head(doc: str, snippet: str) -> str:
    m = _HEAD_RE.search(doc)
    if not m:
        raise ConflictError("no <head> element found")
    return doc[: m.end()] + "\n    " + snippet + doc[m.end():]


def apply_field(doc: str, field_name: str, before: str | None, after: str) -> str:
    """Targeted edit that leaves the rest of the file byte-for-byte unchanged."""
    if field_name == "title":
        m = _TITLE_RE.search(doc)
        _ensure_same(m.group(2) if m else None, before)
        new = html.escape(after, quote=False)
        return doc[: m.start(2)] + new + doc[m.end(2):] if m else _insert_in_head(doc, f"<title>{new}</title>")
    if field_name == "meta_description":
        esc = html.escape(after, quote=True)
        m = _DESC_RE.search(doc)
        if not m:
            _ensure_same(None, before)
            return _insert_in_head(doc, f'<meta name="description" content="{esc}">')
        tag = m.group(0)
        cm = _CONTENT_RE.search(tag)
        _ensure_same(cm.group(2).strip("\"'") if cm else None, before)
        if cm:
            new_tag = tag[: cm.start(2)] + f'"{esc}"' + tag[cm.end(2):]
        else:
            new_tag = tag[:-1].rstrip("/ ") + f' content="{esc}">'
        return doc[: m.start()] + new_tag + doc[m.end():]
    raise ValueError(f"unsupported field: {field_name}")


def _read(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as f:
        return f.read()


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".seo-tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def _log_change(path: Path, event: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": _now(), **event}, ensure_ascii=False) + "\n")


def apply_proposals(proposals_path: Path, adapter: StaticSiteAdapter, out_dir: Path, dry_run: bool = True,
                    auto: bool = False, min_auto_confidence: float = 0.8,
                    print_fn: Callable[..., None] = print) -> dict[str, int]:
    proposals = load_proposals(proposals_path)
    selected = [p for p in proposals if p.status == "approved"]
    auto_ids: set[str] = set()
    if auto:  # automated mode: only clean, high-confidence proposals (AI proposals always carry a warning)
        extra = [p for p in proposals if p.status == "pending" and not p.warnings
                 and p.confidence >= min_auto_confidence]
        auto_ids = {p.id for p in extra}
        selected += extra
    if not selected:
        print_fn("No approved proposals to apply. Run `seo-tool review` first.")
        return {"applied": 0, "skipped": 0}

    by_file: dict[Path, list[Proposal]] = {}
    skipped: list[tuple[Proposal, str]] = []
    for p in selected:
        f = adapter.path_for(p.url)
        if f is None:
            skipped.append((p, "no matching local HTML file"))
        else:
            by_file.setdefault(f, []).append(p)

    backup_dir = out_dir / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest: dict[str, Any] = {"created_at": _now(), "root": str(adapter.root),
                                "proposals_file": str(proposals_path.resolve()), "files": []}
    changelog = out_dir / "changes.log.jsonl"
    applied_count = 0

    for f, items in by_file.items():
        try:
            original = _read(f)
        except UnicodeDecodeError:
            skipped.extend((p, "file is not UTF-8") for p in items)
            continue
        doc, applied = original, []
        for p in items:
            try:
                doc = apply_field(doc, p.field, p.before, p.after)
                applied.append(p)
            except ConflictError as exc:
                skipped.append((p, str(exc)))
        if doc == original:
            continue
        rel = f.relative_to(adapter.root)
        print_fn("\n".join(difflib.unified_diff(original.splitlines(), doc.splitlines(),
                                                f"a/{rel}", f"b/{rel}", lineterm="", n=1)))
        for p in applied:
            print_fn(f"  why ({p.field}): {p.reason}")
        if dry_run:
            continue
        backup = backup_dir / "files" / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, backup)
        _atomic_write(f, doc)
        manifest["files"].append({"path": str(rel), "sha256_before": _sha(original), "sha256_after": _sha(doc),
                                  "proposals": [p.id for p in applied]})
        (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        for p in applied:
            if p.id in auto_ids:
                p.set_status("approved", f"automated mode (confidence >= {min_auto_confidence}, no warnings)")
            p.set_status("applied", f"backup: {backup_dir}")
            _log_change(changelog, {"event": "applied", "proposal": p.id, "url": p.url, "field": p.field,
                                    "before": p.before, "after": p.after, "reason": p.reason, "file": str(rel),
                                    "backup": str(backup_dir), "mode": "auto" if p.id in auto_ids else "approved"})
            applied_count += 1
        log(logger, logging.INFO, "file updated", file=str(rel), proposals=[p.id for p in applied])

    for p, why in skipped:
        print_fn(f"SKIPPED {p.url} [{p.field}]: {why}")
        log(logger, logging.WARNING, "proposal skipped", proposal=p.id, reason=why)
    if not dry_run:
        save_proposals(proposals_path, proposals)
        if manifest["files"]:
            print_fn(f"\nBackup + manifest: {backup_dir}\nRoll back with: seo-tool rollback {backup_dir}")
    return {"applied": applied_count, "skipped": len(skipped)}


def rollback(backup_dir: Path, force: bool = False, print_fn: Callable[..., None] = print) -> int:
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    root = Path(manifest["root"])
    changelog = backup_dir.parent.parent / "changes.log.jsonl"
    restored_ids: set[str] = set()
    for entry in manifest["files"]:
        target, source = root / entry["path"], backup_dir / "files" / entry["path"]
        current = _sha(_read(target)) if target.exists() else None
        if current != entry["sha256_after"] and not force:
            print_fn(f"SKIPPED {entry['path']}: changed since apply (use --force to overwrite)")
            continue
        shutil.copy2(source, target)
        restored_ids.update(entry["proposals"])
        _log_change(changelog, {"event": "rolled_back", "file": entry["path"], "backup": str(backup_dir)})
        print_fn(f"restored {entry['path']}")
    proposals_file = Path(manifest["proposals_file"])
    if restored_ids and proposals_file.exists():
        proposals = load_proposals(proposals_file)
        for p in proposals:
            if p.id in restored_ids:
                p.set_status("rolled_back", f"from {backup_dir}")
        save_proposals(proposals_file, proposals)
    return len(restored_ids)
