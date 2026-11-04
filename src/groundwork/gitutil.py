"""Minimal git helpers via subprocess (no third-party dependency)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout


def is_repo(root: Path) -> bool:
    return _run(root, "rev-parse", "--is-inside-work-tree") is not None


def head(root: Path) -> str | None:
    out = _run(root, "rev-parse", "HEAD")
    return out.strip() if out else None


def user_email(root: Path) -> str | None:
    out = _run(root, "config", "user.email")
    return out.strip() if out else None


def file_history(root: Path, rel: str) -> list[str]:
    """Commits that touched `rel`, oldest first."""
    out = _run(root, "log", "--format=%H", "--reverse", "--", rel)
    return [c for c in (out or "").split() if c]


def show(root: Path, commit: str, rel: str) -> str | None:
    return _run(root, "show", f"{commit}:{rel}")
