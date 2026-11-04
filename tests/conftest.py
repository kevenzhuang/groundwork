import datetime as dt
import subprocess
from pathlib import Path

import pytest

from groundwork.init import init_project

TODAY = dt.date(2026, 11, 4)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "alice@example.org")
    git(tmp_path, "config", "user.name", "Alice")
    git(tmp_path, "config", "commit.gpgsign", "false")
    init_project(tmp_path, "Demo Study", "alice", "Alice", "alice@example.org", today=TODAY)
    return tmp_path


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def commit(root: Path, msg: str = "c") -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", msg)


ROLES_WITH_AGENT = """---
principals:
  - id: alice
    name: Alice
    kind: human
    roles: [owner, lead]
    git_identity: alice@example.org
  - id: bob
    name: Bob
    kind: human
    roles: [advisor]
    git_identity: bob@example.org
  - id: claude-1
    kind: agent
    roles: [agent]
    sponsor: alice
    git_identity: claude-agent@users.noreply.example
---
"""
