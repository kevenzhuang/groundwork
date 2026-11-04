"""Locating a Groundwork project and loading its configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_REL = Path(".groundwork") / "config.yaml"


class NotAProject(RuntimeError):
    pass


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` to the nearest directory containing .groundwork/config.yaml."""
    cur = (start or Path.cwd()).resolve()
    for d in [cur, *cur.parents]:
        if (d / CONFIG_REL).is_file():
            return d
    raise NotAProject(
        f"no Groundwork project found at or above {cur} (missing {CONFIG_REL}); run `gw init`"
    )


def load_config(root: Path) -> dict[str, Any]:
    path = root / CONFIG_REL
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}
