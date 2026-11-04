"""`gw end`: session capture pipeline (spec §8). Deterministic; AI is not required.

collect → classify → draft → ask → confirm → archive
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import gitutil
from .model import FrontMatterError, read_front_matter
from .project import load_config
from .scan import Finding, scan_text

# Record files are excluded from the change list: they are the record, not the work.
RECORD_PREFIXES = ("sessions/", "notes/", ".groundwork/")
NOTE_LINE = re.compile(r"^- (\d{2}:\d{2}) \[([^\]]+)\] (.*)$")
SECTIONS = ("did", "thinking", "blocked", "next", "unverified")
SECTION_TITLES = {
    "did": "Did",
    "thinking": "Thinking",
    "blocked": "Blocked",
    "next": "Next",
    "unverified": "Unverified items touched",
}


@dataclass
class Change:
    status: str  # A, M, D, R, ?? (untracked), or W (uncommitted modification)
    path: str
    committed: bool = True


@dataclass
class Note:
    when: dt.datetime
    principal: str
    text: str
    source: str


@dataclass
class Collected:
    base: str | None
    head: str | None
    changes: list[Change] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    agent_logs: list[Path] = field(default_factory=list)
    since: dt.datetime | None = None


# ---------------------------------------------------------------- collect
def last_session(root: Path) -> tuple[Path, dict[str, Any]] | None:
    d = root / "sessions"
    if not d.is_dir():
        return None
    best = None
    for p in sorted(d.glob("*.md")):
        try:
            fm, _ = read_front_matter(p)
        except FrontMatterError:
            continue
        if not fm.get("confirmed_by"):
            continue
        key = str(fm.get("ended_at") or fm.get("date") or "")
        if best is None or key >= best[0]:
            best = (key, p, fm)
    return (best[1], best[2]) if best else None


def _parse_ts(v: Any) -> dt.datetime | None:
    if isinstance(v, dt.datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, dt.date):
        return dt.datetime.combine(v, dt.time.max)
    if isinstance(v, str):
        try:
            return dt.datetime.fromisoformat(v).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _is_record(path: str) -> bool:
    return path.startswith(RECORD_PREFIXES) or path.endswith(".gitkeep")


def adoption_commit(root: Path) -> str | None:
    """The commit that first added .groundwork/config.yaml: where the record begins."""
    hist = gitutil.file_history(root, ".groundwork/config.yaml")
    return hist[0] if hist else None


def group_changes(changes: list[Change], threshold: int = 8) -> dict[str, list[Change]]:
    """Group by top-level directory when there are many changes, so we ask once per group."""
    if len(changes) <= threshold:
        return {c.path: [c] for c in changes}
    groups: dict[str, list[Change]] = {}
    for c in changes:
        key = c.path.split("/", 1)[0] + "/" if "/" in c.path else c.path
        groups.setdefault(key, []).append(c)
    return groups


def collect_git(root: Path, base: str | None) -> tuple[str | None, list[Change]]:
    head = gitutil.head(root)
    changes: list[Change] = []
    if head:
        if base and base != head:
            out = gitutil._run(root, "diff", "--name-status", "-M", f"{base}..{head}") or ""
        elif base == head:
            out = ""
        else:  # first session: everything in history
            out = gitutil._run(root, "log", "--name-status", "--format=", "--reverse") or ""
        seen: dict[str, Change] = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status, path = parts[0][0], parts[-1]
            if not _is_record(path):
                seen[path] = Change(status, path)
        changes = list(seen.values())
    status = gitutil._run(root, "status", "--porcelain", "--untracked-files=all") or ""
    for line in status.splitlines():
        code, path = line[:2], line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if _is_record(path) or any(c.path == path for c in changes):
            continue
        changes.append(Change("??" if code == "??" else "W", path, committed=False))
    return head, changes


def collect_notes(root: Path, since: dt.datetime | None) -> list[Note]:
    d = root / "notes"
    notes: list[Note] = []
    if not d.is_dir():
        return notes
    for p in sorted(d.glob("*.md")):
        try:
            day = dt.date.fromisoformat(p.stem)
        except ValueError:
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = NOTE_LINE.match(line)
            if not m:
                continue
            hh, mm = map(int, m.group(1).split(":"))
            when = dt.datetime.combine(day, dt.time(hh, mm))
            if since is None or when > since:
                notes.append(Note(when, m.group(2), m.group(3), f"repo:notes/{p.name}#L{n}"))
    return notes


def claude_log_dir(root: Path) -> Path:
    """Claude Code stores transcripts at ~/.claude/projects/<cwd with / → ->/*.jsonl."""
    base = Path(os.environ.get("GW_CLAUDE_DIR", Path.home() / ".claude" / "projects"))
    return base / re.sub(r"[^A-Za-z0-9]", "-", str(root.resolve()))


def collect_agent_logs(root: Path, since: dt.datetime | None) -> list[Path]:
    d = claude_log_dir(root)
    if not d.is_dir():
        return []
    cutoff = since.timestamp() if since else 0
    return sorted(p for p in d.glob("*.jsonl") if p.stat().st_mtime > cutoff)


def collect(root: Path, include_agent_logs: bool = True) -> Collected:
    prev = last_session(root)
    base = None
    since = None
    if prev:
        base = prev[1].get("head")
        since = _parse_ts(prev[1].get("ended_at")) or _parse_ts(prev[1].get("date"))
    else:
        base = adoption_commit(root)  # first session: work since Groundwork was adopted
    head, changes = collect_git(root, base)
    return Collected(
        base=base,
        head=head,
        changes=changes,
        notes=collect_notes(root, since),
        agent_logs=collect_agent_logs(root, since) if include_agent_logs else [],
        since=since,
    )


# ---------------------------------------------------------------- classify
class Blocked(RuntimeError):
    def __init__(self, findings: list[Finding]):
        self.findings = findings
        kinds = ", ".join(sorted({f.kind for f in findings}))
        super().__init__(f"possible confidential content ({kinds}); session not written")


def classify(root: Path, texts: list[str]) -> list[Finding]:
    cfg = load_config(root)
    out: list[Finding] = []
    for t in texts:
        out.extend(scan_text(t, Path("session"), cfg.get("blocklist"), cfg.get("email_allowlist")))
    return [f for f in out if f.kind.startswith("secret:") or f.kind == "blocklist"]


# ---------------------------------------------------------------- archive
def archive_dir(root: Path) -> Path:
    cfg = load_config(root)
    raw = cfg.get("archive_dir") or f"~/.gw/archive/{cfg.get('project_id', 'project')}"
    return Path(os.path.expanduser(str(raw)))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_files(root: Path, files: list[Path], stamp: str) -> list[str]:
    """Copy raw files to the local archive; return archive: pointers (spec §8.3–8.4)."""
    dest_root = archive_dir(root)
    pointers = []
    for f in files:
        rel = Path(stamp) / f.name
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        pointers.append(f"archive:{rel.as_posix()}@sha256:{sha256(dest)}")
    return pointers


# ---------------------------------------------------------------- draft
def session_path(root: Path, principal: str, day: dt.date) -> Path:
    d = root / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    stem = f"{day.isoformat()}-{principal}"
    p = d / f"{stem}.md"
    n = 2
    while p.exists():
        try:
            fm, _ = read_front_matter(p)
        except FrontMatterError:
            fm = {}
        if not fm.get("confirmed_by"):  # reuse today's unconfirmed draft
            return p
        p = d / f"{stem}-{n}.md"
        n += 1
    return p


_LABEL = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed",
          "W": "uncommitted", "??": "new, untracked"}


def render(
    principal: str,
    col: Collected,
    answers: dict[str, Any],
    sources: list[str],
    now: dt.datetime,
    confirmed_by: str | None,
) -> str:
    reasons: dict[str, str] = answers.get("reasons") or {}
    fm: dict[str, Any] = {
        "principal": principal,
        "date": now.date().isoformat(),
        "ended_at": now.replace(microsecond=0).isoformat(),
        "capture": "contemporaneous",
        "base": col.base,
        "head": col.head,
        "confirmed_by": confirmed_by,
        "sources": sources,
        "classification": answers.get("classification", "internal"),
    }
    lines = ["---", yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip(), "---", ""]
    for key in ("did", "thinking"):
        lines += [f"## {SECTION_TITLES[key]}", "", (answers.get(key) or "").strip() or "_(blank)_", ""]
    lines += ["## Changes and reasons", ""]
    if not col.changes:
        lines.append("_No file changes since the last session._")
    for c in col.changes:
        why = (reasons.get(c.path) or "").strip()
        lines.append(f"- `{c.path}` ({_LABEL.get(c.status, c.status)}): {why or '**reason not given**'}")
    if col.notes:
        lines += ["", "Notes written during the session:", ""]
        lines += [f"- {n.when:%Y-%m-%d %H:%M} [{n.principal}] {n.text}" for n in col.notes]
    lines.append("")
    for key in ("blocked", "next", "unverified"):
        lines += [f"## {SECTION_TITLES[key]}", "", (answers.get(key) or "").strip() or "_(blank)_", ""]
    return "\n".join(lines)


def write_session(
    root: Path,
    principal: str,
    col: Collected,
    answers: dict[str, Any],
    confirm: bool,
    now: dt.datetime | None = None,
    archive: bool = True,
) -> Path:
    now = now or dt.datetime.now()
    texts = [str(v) for k, v in answers.items() if k != "reasons" and v]
    texts += [str(v) for v in (answers.get("reasons") or {}).values() if v]
    hard = classify(root, texts)
    if hard:
        raise Blocked(hard)
    sources: list[str] = []
    if col.base and col.head:
        sources.append(f"commit:{col.base}..{col.head}")
    elif col.head:
        sources.append(f"commit:{col.head}")
    sources += sorted({n.source.split("#")[0] for n in col.notes})
    if archive and col.agent_logs:
        sources += archive_files(root, col.agent_logs, now.strftime("%Y%m%dT%H%M%S"))
    path = session_path(root, principal, now.date())
    path.write_text(render(principal, col, answers, sources, now, principal if confirm else None),
                    encoding="utf-8")
    return path


def missing_reasons(col: Collected, answers: dict[str, Any]) -> list[str]:
    reasons = answers.get("reasons") or {}
    return [c.path for c in col.changes if not (reasons.get(c.path) or "").strip()]
