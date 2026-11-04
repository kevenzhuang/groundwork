"""`gw init`: create the project layout from templates (spec §2)."""

from __future__ import annotations

import datetime as dt
import re
from importlib import resources
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from . import SPEC_VERSION, gitutil

EMPTY_DIRS = ["timeline", "sessions", "handoffs", "notes"]


def spec_text() -> str:
    """Spec bundled in the wheel; falls back to the source tree during development."""
    try:
        return resources.files("groundwork").joinpath("data/SPEC.md").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        here = Path(__file__).resolve()
        for parent in here.parents:
            cand = parent / "spec" / "SPEC.md"
            if cand.is_file():
                return cand.read_text(encoding="utf-8")
    raise FileNotFoundError("SPEC.md not found in package or source tree")


def slugify(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower()).strip("-")
    return s or "project"


def _walk(node, prefix: str = ""):
    for child in node.iterdir():
        rel = f"{prefix}{child.name}"
        if child.is_dir():
            yield from _walk(child, rel + "/")
        else:
            yield rel, child


def init_project(
    target: Path,
    title: str,
    owner_id: str,
    owner_name: str,
    owner_git: str | None = None,
    force: bool = False,
    today: dt.date | None = None,
) -> list[Path]:
    """Render templates into `target`. Never overwrites existing files unless force=True."""
    target.mkdir(parents=True, exist_ok=True)
    ctx = {
        "title": title,
        "project_id": slugify(title),
        "owner_id": owner_id,
        "owner_name": owner_name,
        "owner_git": owner_git or gitutil.user_email(target) or "",
        "date": (today or dt.date.today()).isoformat(),
        "spec_version": SPEC_VERSION,
    }
    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True, autoescape=False)
    root = resources.files("groundwork").joinpath("templates/project")
    written: list[Path] = []
    for rel, res in sorted(_walk(root)):
        dest = target / rel
        if dest.exists() and not force:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = res.read_text(encoding="utf-8")
        dest.write_text(env.from_string(text).render(**ctx), encoding="utf-8")
        written.append(dest)
    spec_dest = target / ".groundwork" / "SPEC.md"
    if force or not spec_dest.exists():
        spec_dest.write_text(spec_text(), encoding="utf-8")
        written.append(spec_dest)
    (target / ".groundwork" / "spec-version").write_text(SPEC_VERSION + "\n", encoding="utf-8")
    for d in EMPTY_DIRS:
        keep = target / d / ".gitkeep"
        if not keep.exists():
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.touch()
    return written
