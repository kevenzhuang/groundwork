"""Enumerations and record parsing shared by all commands (spec §1, §3)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROLES = {"owner", "lead", "advisor", "contributor", "receiver", "agent"}
KINDS = {"human", "agent"}
TIERS = {"T0", "T1", "T2", "T3"}
DECISION_STATUSES = {"proposed", "accepted", "vetoed", "superseded"}
VERIFICATION_STATUSES = {"unverified", "auto-checked", "human-verified", "disputed", "retracted"}
CAPTURES = {"contemporaneous", "reconstructed"}
CLASSIFICATIONS = {"public", "internal", "restricted", "secret"}

LEDGER_REQUIRED_COLUMNS = [
    "id", "status", "provenance", "verified_by", "verified_on",
    "method", "evidence", "classification", "notes",
]

REQUIRED_FILES = ["PROJECT.md", "ROLES.md", "DECISION-RIGHTS.md", "AGENTS.md"]

ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
GITHUB_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
FMT = "[E12] "  # prefix marking identity-format problems (spec §3.2)

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


class FrontMatterError(ValueError):
    pass


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Return (front-matter dict, body). Missing front-matter yields ({}, text)."""
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise FrontMatterError(str(exc)) from exc
    if not isinstance(data, dict):
        raise FrontMatterError("front-matter is not a mapping")
    return data, text[m.end():]


def read_front_matter(path: Path) -> tuple[dict[str, Any], str]:
    return split_front_matter(path.read_text(encoding="utf-8"))


@dataclass
class Principal:
    id: str
    kind: str
    roles: list[str]
    name: str = ""
    sponsor: str | None = None
    git_identity: str | None = None
    signing_key: str | None = None
    github: str | None = None
    aliases: list[str] = field(default_factory=list)
    orcid: str | None = None

    @property
    def is_agent(self) -> bool:
        return self.kind == "agent"


@dataclass
class Roster:
    principals: dict[str, Principal] = field(default_factory=dict)

    def get(self, pid: Any) -> Principal | None:
        return self.principals.get(str(pid)) if pid is not None else None

    def owners(self) -> list[Principal]:
        return [p for p in self.principals.values() if "owner" in p.roles]

    def is_human(self, pid: Any) -> bool:
        p = self.get(pid)
        return p is not None and p.kind == "human"

    def is_agent(self, pid: Any) -> bool:
        p = self.get(pid)
        return p is not None and p.kind == "agent"

    def resolve(self, text: Any) -> list[Principal]:
        """Map what a human might say ("Arnold", "王老师", "@arnold-gh") to principals.
        Exact id first; otherwise case-insensitive match on id, name, aliases, github."""
        if text is None:
            return []
        q = str(text).strip().lstrip("@").lower()
        if not q:
            return []
        exact = self.principals.get(q)
        if exact:
            return [exact]
        hits = []
        for p in self.principals.values():
            keys = {p.id.lower(), p.name.lower(), (p.github or "").lower(), *(a.lower() for a in p.aliases)}
            if q in keys or any(q and q in k.split() for k in keys if k):
                hits.append(p)
        return hits


def _suggest_id(raw: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    if not s or not s[0].isalpha():
        s = "p-" + s if s else "member"
    return s[:32]


def parse_roster(data: dict[str, Any]) -> tuple[Roster, list[str]]:
    """Build a Roster from ROLES.md front-matter. Returns (roster, problems)."""
    problems: list[str] = []
    roster = Roster()
    entries = data.get("principals")
    if not isinstance(entries, list) or not entries:
        return roster, ["`principals` must be a non-empty list"]
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"principals[{i}] is not a mapping")
            continue
        pid = e.get("id")
        if not pid:
            problems.append(f"principals[{i}] has no id")
            continue
        pid = str(pid)
        if not ID_RE.match(pid):
            problems.append(f"{FMT}`{pid}`: id must be lowercase letters, digits and hyphens, 2–32 chars, "
                            f"starting with a letter (e.g. `{_suggest_id(pid)}`); put the full name in `name`")
        if pid.lower() in {k.lower() for k in roster.principals}:
            problems.append(f"duplicate principal id `{pid}` (ids are compared case-insensitively)")
        if not str(e.get("name") or "").strip():
            problems.append(f"`{pid}`: `name` is required (any language or format)")
        gh = str(e["github"]).lstrip("@") if e.get("github") else None
        if gh and not GITHUB_RE.match(gh):
            problems.append(f"{FMT}`{pid}`: `github` is not a valid GitHub login: {gh!r}")
        orcid = str(e["orcid"]).strip() if e.get("orcid") else None
        if orcid:
            orcid = re.sub(r"^https?://orcid\.org/", "", orcid)
            if not ORCID_RE.match(orcid):
                problems.append(f"{FMT}`{pid}`: `orcid` must look like 0000-0000-0000-000X: {orcid!r}")
        aliases = e.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        kind = e.get("kind")
        if kind not in KINDS:
            problems.append(f"`{pid}`: kind must be one of {sorted(KINDS)}")
        roles = e.get("roles") or []
        if isinstance(roles, str):
            roles = [roles]
        bad = [r for r in roles if r not in ROLES]
        if bad:
            problems.append(f"`{pid}`: unknown role(s) {bad}")
        if kind == "agent" and "owner" in roles:
            problems.append(f"`{pid}`: an agent cannot be owner")
        roster.principals[pid] = Principal(
            id=pid,
            kind=kind or "",
            roles=list(roles),
            name=str(e.get("name") or ""),
            sponsor=str(e["sponsor"]) if e.get("sponsor") else None,
            git_identity=e.get("git_identity"),
            signing_key=e.get("signing_key"),
            github=gh,
            aliases=[str(a) for a in aliases],
            orcid=orcid,
        )
    for p in roster.principals.values():
        if p.kind == "agent":
            if not p.sponsor:
                problems.append(f"agent `{p.id}` has no sponsor")
            elif not roster.is_human(p.sponsor):
                problems.append(f"agent `{p.id}`: sponsor `{p.sponsor}` is not a known human")
    n_owner = len(roster.owners())
    if n_owner != 1:
        problems.append(f"exactly one owner required, found {n_owner}")
    return roster, problems
