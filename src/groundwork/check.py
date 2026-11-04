"""`gw check`: validate a project against the spec (§7). Deterministic, offline."""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import gitutil
from .model import (
    CAPTURES,
    CLASSIFICATIONS,
    DECISION_STATUSES,
    LEDGER_REQUIRED_COLUMNS,
    REQUIRED_FILES,
    TIERS,
    VERIFICATION_STATUSES,
    FrontMatterError,
    Roster,
    parse_roster,
    read_front_matter,
    split_front_matter,
)
from .project import load_config
from .scan import scan_tree


@dataclass
class Issue:
    code: str
    level: str  # "error" | "warning"
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


class Checker:
    def __init__(self, root: Path, today: dt.date | None = None):
        self.root = root
        self.config = load_config(root)
        self.today = today or dt.date.today()
        self.issues: list[Issue] = []
        self.roster = Roster()

    # ---- helpers -------------------------------------------------------
    def _rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    def err(self, code: str, path: str, msg: str) -> None:
        self.issues.append(Issue(code, "error", path, msg))

    def warn(self, code: str, path: str, msg: str) -> None:
        self.issues.append(Issue(code, "warning", path, msg))

    def _fm(self, p: Path) -> dict[str, Any] | None:
        try:
            fm, _ = read_front_matter(p)
            return fm
        except FrontMatterError as exc:
            self.err("E10", self._rel(p), f"invalid front-matter: {exc}")
            return None

    def _enum(self, path: str, field: str, value: Any, allowed: set[str], required: bool = False) -> None:
        if value in (None, ""):
            if required:
                self.err("E10", path, f"`{field}` is required")
            return
        if str(value) not in allowed:
            self.err("E10", path, f"`{field}`={value!r} not in {sorted(allowed)}")

    # ---- checks --------------------------------------------------------
    def run(self) -> list[Issue]:
        self.check_required_files()
        self.check_roles()
        self.check_decision_rights()
        self.check_decisions()
        self.check_ledger()
        self.check_sessions()
        self.check_questions()
        self.check_confidentiality()
        self.check_integrity()
        order = {"error": 0, "warning": 1}
        self.issues.sort(key=lambda i: (order[i.level], i.code, i.path))
        return self.issues

    def check_required_files(self) -> None:
        for f in REQUIRED_FILES:
            if not (self.root / f).is_file():
                self.err("E01", f, "required file is missing")

    def check_roles(self) -> None:
        p = self.root / "ROLES.md"
        if not p.is_file():
            return
        fm = self._fm(p)
        if fm is None:
            return
        self.roster, problems = parse_roster(fm)
        for msg in problems:
            self.err("E02", "ROLES.md", msg)

    def check_decision_rights(self) -> None:
        p = self.root / "DECISION-RIGHTS.md"
        if not p.is_file():
            return
        fm = self._fm(p)
        if fm is None:
            return
        for i, a in enumerate(fm.get("areas") or []):
            if isinstance(a, dict):
                self._enum("DECISION-RIGHTS.md", f"areas[{i}].tier", a.get("tier"), TIERS, required=True)
        if not fm.get("confirmed_by"):
            self.warn("W01", "DECISION-RIGHTS.md", "not yet confirmed by the owner")
        elif self.roster.principals and "owner" not in (
            (self.roster.get(fm["confirmed_by"]) or _NoRoles).roles
        ):
            self.err("E02", "DECISION-RIGHTS.md", f"confirmed_by `{fm['confirmed_by']}` is not the owner")

    def check_decisions(self) -> None:
        d = self.root / "decisions"
        if not d.is_dir():
            return
        seen: dict[str, str] = {}
        for p in sorted(d.glob("*.md")):
            rel = self._rel(p)
            fm = self._fm(p)
            if fm is None:
                continue
            did = str(fm.get("id") or "")
            if not did:
                self.err("E03", rel, "`id` is required")
            elif did in seen:
                self.err("E03", rel, f"duplicate decision id {did} (also {seen[did]})")
            else:
                seen[did] = rel
            for key in ("date", "title"):
                if not fm.get(key):
                    self.err("E03", rel, f"`{key}` is required")
            tier = fm.get("tier")
            self._enum(rel, "tier", tier, TIERS, required=True)
            self._enum(rel, "status", fm.get("status"), DECISION_STATUSES, required=True)
            self._enum(rel, "capture", fm.get("capture"), CAPTURES, required=True)
            self._enum(rel, "classification", fm.get("classification"), CLASSIFICATIONS)
            decider = fm.get("decider")
            if tier == "T0":
                if not fm.get("proposed_by"):
                    self.err("E03", rel, "T0 proposal requires `proposed_by`")
                if fm.get("status") not in (None, "proposed", "vetoed", "superseded"):
                    self.err("E03", rel, "a T0 proposal cannot be `accepted`; a human must decide at T1–T3")
            elif tier in TIERS:
                if not decider:
                    self.err("E03", rel, f"{tier} requires `decider`")
                elif self.roster.principals and not self.roster.is_human(decider):
                    kind = "an agent" if self.roster.is_agent(decider) else "not a known human"
                    self.err("E04", rel, f"decider `{decider}` is {kind}")
            if tier == "T2":
                for key in ("notified", "veto_window"):
                    if not fm.get(key):
                        self.err("E03", rel, f"T2 requires `{key}`")
            if tier == "T3":
                ab = fm.get("approved_by")
                if not ab:
                    self.err("E03", rel, "T3 requires `approved_by`")
                elif self.roster.principals and not self.roster.is_human(ab):
                    self.err("E04", rel, f"approved_by `{ab}` is not a known human")
            sup = fm.get("supersedes")
            if sup and str(sup) not in seen and not any(
                str(sup) == str((self._fm(q) or {}).get("id")) for q in d.glob("*.md")
            ):
                self.err("E03", rel, f"supersedes unknown decision `{sup}`")

    def check_ledger(self) -> None:
        d = self.root / "ledger"
        if not d.is_dir():
            return
        for p in sorted(d.glob("*.csv")):
            rel = self._rel(p)
            with p.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                cols = reader.fieldnames or []
                missing = [c for c in LEDGER_REQUIRED_COLUMNS if c not in cols]
                if missing:
                    self.err("E10", rel, f"missing required column(s): {missing}")
                    continue
                ids: set[str] = set()
                for n, row in enumerate(reader, start=2):
                    loc = f"{rel}:{n}"
                    rid = (row.get("id") or "").strip()
                    if not rid:
                        self.err("E10", loc, "empty id")
                    elif rid in ids:
                        self.err("E10", loc, f"duplicate id {rid}")
                    ids.add(rid)
                    status = (row.get("status") or "").strip()
                    self._enum(loc, "status", status, VERIFICATION_STATUSES, required=True)
                    self._enum(loc, "classification", (row.get("classification") or "").strip() or None,
                               CLASSIFICATIONS)
                    vb = (row.get("verified_by") or "").strip()
                    if status == "human-verified":
                        for key in ("verified_by", "verified_on", "method"):
                            if not (row.get(key) or "").strip():
                                self.err("E05", loc, f"human-verified requires `{key}`")
                    if vb and self.roster.principals:
                        if self.roster.is_agent(vb):
                            self.err("E06", loc, f"verified_by `{vb}` is an agent")
                        elif not self.roster.is_human(vb):
                            self.err("E06", loc, f"verified_by `{vb}` is not a known human")

    def check_sessions(self) -> None:
        d = self.root / "sessions"
        if not d.is_dir():
            return
        for p in sorted(d.glob("*.md")):
            fm = self._fm(p)
            if fm is None:
                continue
            rel = self._rel(p)
            self._enum(rel, "capture", fm.get("capture"), CAPTURES)
            if not fm.get("confirmed_by"):
                self.warn("W04", rel, "session draft not yet confirmed")
            elif self.roster.principals and not self.roster.is_human(fm["confirmed_by"]):
                self.err("E04", rel, f"confirmed_by `{fm['confirmed_by']}` is not a known human")

    def check_questions(self) -> None:
        p = self.root / "open-questions.md"
        if not p.is_file():
            return
        fm = self._fm(p) or {}
        for q in fm.get("questions") or []:
            if not isinstance(q, dict) or q.get("status", "open") != "open":
                continue
            date = q.get("date")
            if isinstance(date, str):
                try:
                    date = dt.date.fromisoformat(date)
                except ValueError:
                    date = None
            if isinstance(date, dt.date) and (self.today - date).days > 30:
                self.warn("W02", "open-questions.md", f"{q.get('id')} open for {(self.today - date).days} days")

    def check_confidentiality(self) -> None:
        cfg = dict(self.config)
        allow = list(cfg.get("email_allowlist") or [])
        allow += [p.git_identity for p in self.roster.principals.values() if p.git_identity]
        cfg["email_allowlist"] = allow
        for f in scan_tree(self.root, cfg):
            rel = f"{self._rel(f.path)}:{f.line}"
            if f.kind == "blocklist":
                self.err("E08", rel, f"blocklisted term `{f.kind and f.excerpt}`")
            elif f.kind.startswith("secret:"):
                self.err("E07", rel, f"possible {f.kind[7:]} ({f.excerpt})")
            else:
                self.warn("W05", rel, f"{f.kind} found ({f.excerpt}); redact, mark restricted, or allowlist")

    def check_integrity(self) -> None:
        """E09: frozen records must not change after acceptance/confirmation (spec §3.4, §10.1)."""
        if not gitutil.is_repo(self.root):
            return
        frozen = [
            ("decisions", lambda fm: fm.get("status") in ("accepted", "vetoed"), {"status", "superseded_by"}),
            ("sessions", lambda fm: bool(fm.get("confirmed_by")), set()),
            ("handoffs", lambda fm: bool(fm.get("confirmed_by_from")), {"approved_by"}),
        ]
        for folder, is_frozen, mutable in frozen:
            d = self.root / folder
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.md")):
                rel = self._rel(p)
                baseline = None
                for c in gitutil.file_history(self.root, rel):
                    text = gitutil.show(self.root, c, rel)
                    if text is None:
                        continue
                    try:
                        fm, body = split_front_matter(text)
                    except FrontMatterError:
                        continue
                    if is_frozen(fm):
                        baseline = (fm, body, c)
                        break
                if baseline is None:
                    continue
                try:
                    cur_fm, cur_body = read_front_matter(p)
                except FrontMatterError:
                    continue
                b_fm, b_body, commit = baseline
                strip = lambda m: {k: v for k, v in m.items() if k not in mutable}  # noqa: E731
                if strip(b_fm) != strip(cur_fm) or b_body.strip() != cur_body.strip():
                    self.err("E09", rel, f"modified after it was frozen in {commit[:8]}; "
                                         "write a new entry that supersedes it instead")
                if folder == "decisions" and cur_fm.get("status") not in (b_fm.get("status"), "superseded"):
                    self.err("E09", rel, f"status changed {b_fm.get('status')} → {cur_fm.get('status')}")


class _NoRoles:
    roles: list[str] = []


def run_check(root: Path, today: dt.date | None = None) -> list[Issue]:
    return Checker(root, today).run()
