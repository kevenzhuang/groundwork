"""Versioning and upgrades (spec §16).

- project_spec(): the spec version a project declares
- RULE_SINCE: when each rule became part of the spec (newer rules only warn on older projects)
- upgrade(): bring a project to the installed tool's spec, deterministically and offline
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml

from . import SPEC_VERSION, __version__, vtuple

# Rule code → spec version that introduced it.
RULE_SINCE: dict[str, str] = {
    "E12": "0.3",
}

PIN = re.compile(r"(github\.com/kevenzhuang/groundwork)(@v[0-9][0-9A-Za-z.\-]*)?")

DEFAULT_CONFIG_KEYS = {
    "language": "auto",
    "archive_agent_logs": False,
}


def project_spec(root: Path) -> str:
    f = root / ".groundwork" / "spec-version"
    if f.is_file():
        v = f.read_text(encoding="utf-8").strip()
        if v:
            return v
    return "0.2"


def is_newer_rule(code: str, project_version: str) -> bool:
    since = RULE_SINCE.get(code)
    return since is not None and vtuple(project_version) < vtuple(since)


def changelog_between(old: str, new: str) -> list[str]:
    """Changelog sections for versions in (old, new]."""
    try:
        text = resources.files("groundwork").joinpath("data/CHANGELOG.md").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        here = Path(__file__).resolve()
        cand = next((p / "CHANGELOG.md" for p in here.parents if (p / "CHANGELOG.md").is_file()), None)
        if cand is None:
            return []
        text = cand.read_text(encoding="utf-8")
    out: list[str] = []
    keep = False
    for line in text.splitlines():
        m = re.match(r"^## \[?v?([0-9][0-9.]*)", line)
        if m:
            spec = vtuple(m.group(1))[:2]  # tool 0.3.x implements spec 0.3
            keep = vtuple(old)[:2] < spec <= vtuple(new)[:2]
        if keep:
            out.append(line)
    return out


@dataclass
class UpgradeResult:
    old: str
    new: str
    changed: list[str] = field(default_factory=list)
    changelog: list[str] = field(default_factory=list)

    @property
    def up_to_date(self) -> bool:
        return not self.changed


def upgrade(root: Path, dry_run: bool = False) -> UpgradeResult:
    from .init import spec_text

    old = project_spec(root)
    res = UpgradeResult(old=old, new=SPEC_VERSION)
    if vtuple(old) > vtuple(SPEC_VERSION):
        raise RuntimeError(f"this project follows spec {old}, newer than the installed tool "
                           f"(spec {SPEC_VERSION}); upgrade the tool instead")

    def write(rel: str, text: str) -> None:
        p = root / rel
        if p.is_file() and p.read_text(encoding="utf-8") == text:
            return
        res.changed.append(rel)
        if not dry_run:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    write(".groundwork/SPEC.md", spec_text())
    write(".groundwork/spec-version", SPEC_VERSION + "\n")

    wf = root / ".github" / "workflows" / "groundwork.yml"
    if wf.is_file():
        text = wf.read_text(encoding="utf-8")
        write(".github/workflows/groundwork.yml", PIN.sub(lambda m: f"{m.group(1)}@v{__version__}", text))

    cfg_path = root / ".groundwork" / "config.yaml"
    if cfg_path.is_file():
        raw = cfg_path.read_text(encoding="utf-8")
        cfg = yaml.safe_load(raw) or {}
        missing = {k: v for k, v in DEFAULT_CONFIG_KEYS.items() if k not in cfg}
        if missing:
            extra = "\n# Added by `gw upgrade` to spec " + SPEC_VERSION + "\n" + yaml.safe_dump(missing, sort_keys=False)
            write(".groundwork/config.yaml", raw.rstrip("\n") + "\n" + extra)

    res.changelog = changelog_between(old, SPEC_VERSION) if res.changed else []
    return res
