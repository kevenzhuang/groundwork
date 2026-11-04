"""`gw approvals`: verify that file-declared approvals match GitHub PR reviews (spec §13.3).

Inputs are plain data so the check is deterministic and testable offline:
- the list of files changed by the pull request,
- the pull request's reviews as returned by the GitHub REST API
  (GET /repos/{owner}/{repo}/pulls/{n}/reviews): [{"user": {"login": ...}, "state": "APPROVED"}, ...]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import FrontMatterError, parse_roster, read_front_matter, split_front_matter


@dataclass
class ApprovalIssue:
    path: str
    message: str


def approved_logins(reviews: list[dict[str, Any]]) -> set[str]:
    """Latest review state per user; APPROVED counts unless superseded by CHANGES_REQUESTED/DISMISSED."""
    latest: dict[str, str] = {}
    for r in reviews:
        login = ((r.get("user") or {}).get("login") or "").lower()
        state = str(r.get("state") or "").upper()
        if login and state in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[login] = state
    return {u for u, s in latest.items() if s == "APPROVED"}


def _names(v: Any) -> list[str]:
    if v is None or v == "":
        return []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


GOVERNANCE_FILES = ("ROLES.md", "DECISION-RIGHTS.md")


def verify(root: Path, changed: list[str], reviews: list[dict[str, Any]],
           author: str | None = None, base_roles: str | None = None) -> list[ApprovalIssue]:
    """`base_roles` is ROLES.md as it was before the PR. Identities used to verify approvals come
    from it whenever possible, so a PR cannot make someone owner (or change a login) and then
    rely on that change to approve itself."""
    head, _ = parse_roster(read_front_matter(root / "ROLES.md")[0])
    base = parse_roster(split_front_matter(base_roles)[0])[0] if base_roles else None
    approved = approved_logins(reviews)
    author = (author or "").lower()
    issues: list[ApprovalIssue] = []

    def lookup(pid: str):
        return (base.get(pid) if base else None) or head.get(pid)

    def approved_by(pr) -> bool:
        login = (pr.github or "").lower()
        return bool(login) and (login in approved or login == author)

    # Governance files: changes need the owner's approval (spec §3.3 default: `rules` is T3 by owner).
    touched = [f for f in GOVERNANCE_FILES if f in changed]
    if touched:
        owners = (base or head).owners()
        if not owners:
            issues.append(ApprovalIssue(touched[0], "no owner to approve changes to roles/decision rights"))
        else:
            owner = owners[0]
            if not owner.github:
                issues.append(ApprovalIssue(touched[0], f"owner `{owner.id}` has no `github` login; "
                                                        "cannot verify approval of " + ", ".join(touched)))
            elif not approved_by(owner):
                issues.append(ApprovalIssue(touched[0], f"changes to {', '.join(touched)} need approval from "
                                                        f"the owner `{owner.id}` (@{owner.github})"))

    for rel in changed:
        if not (rel.startswith("decisions/") and rel.endswith(".md")):
            continue
        p = root / rel
        if not p.is_file():
            continue
        try:
            fm, _ = read_front_matter(p)
        except FrontMatterError as exc:
            issues.append(ApprovalIssue(rel, f"invalid front-matter: {exc}"))
            continue
        if fm.get("status") != "accepted" or fm.get("tier") not in ("T2", "T3"):
            continue
        for pid in _names(fm.get("approved_by")):
            pr = lookup(pid)
            if pr is None:
                issues.append(ApprovalIssue(rel, f"approved_by `{pid}` is not in ROLES.md"))
            elif not pr.github:
                issues.append(ApprovalIssue(rel, f"`{pid}` has no `github` login in ROLES.md; cannot verify approval"))
            elif not approved_by(pr):
                # GitHub does not let authors review their own PR; an authenticated author counts as approving
                issues.append(ApprovalIssue(rel, f"approved_by `{pid}` (@{pr.github}) has not approved this pull request"))
    return issues
