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
        if pid in roster.principals:
            problems.append(f"duplicate principal id `{pid}`")
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
            github=str(e["github"]).lstrip("@") if e.get("github") else None,
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
