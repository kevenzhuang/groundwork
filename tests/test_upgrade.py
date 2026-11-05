import re

import pytest
from conftest import TODAY, write
from typer.testing import CliRunner

from groundwork import SPEC_VERSION, __version__
from groundwork.check import run_check
from groundwork.cli import app
from groundwork.status import briefing
from groundwork.upgrade import changelog_between, project_spec, upgrade

BAD_ROLES = """---
principals:
  - {id: alice, name: Alice, kind: human, roles: [owner]}
  - {id: Bob Li, name: Bob, kind: human, roles: [advisor]}
---
"""


def make_old(root):
    """Simulate a project created by an older tool: spec 0.2, unpinned workflow, old config."""
    (root / ".groundwork/spec-version").write_text("0.2\n")
    wf = root / ".github/workflows/groundwork.yml"
    wf.write_text(re.sub(r"groundwork@v[0-9.]+", "groundwork", wf.read_text()))
    cfg = root / ".groundwork/config.yaml"
    cfg.write_text("\n".join(l for l in cfg.read_text().splitlines()
                             if not l.startswith(("language:", "archive_agent_logs:"))) + "\n")


def levels(root, code):
    return {i.level for i in run_check(root, today=TODAY) if i.code == code}


def test_init_pins_current_version(project):
    assert project_spec(project) == SPEC_VERSION
    assert f"groundwork@v{__version__}" in (project / ".github/workflows/groundwork.yml").read_text()


def test_new_rule_only_warns_on_older_project(project):
    make_old(project)
    write(project, "ROLES.md", BAD_ROLES)
    assert levels(project, "E12") == {"warning"}
    msg = next(i.message for i in run_check(project, today=TODAY) if i.code == "E12")
    assert "gw upgrade" in msg


def test_upgrade_makes_new_rule_an_error_and_updates_files(project):
    make_old(project)
    write(project, "ROLES.md", BAD_ROLES)
    res = upgrade(project)
    assert res.old == "0.2" and res.new == SPEC_VERSION
    assert {".groundwork/spec-version", ".github/workflows/groundwork.yml",
            ".groundwork/config.yaml"} <= set(res.changed)
    assert f"groundwork@v{__version__}" in (project / ".github/workflows/groundwork.yml").read_text()
    cfg = (project / ".groundwork/config.yaml").read_text()
    assert "language: auto" in cfg and "archive_agent_logs: false" in cfg
    assert levels(project, "E12") == {"error"}
    assert any("0.3.0" in l for l in res.changelog)


def test_upgrade_is_idempotent_and_dry_run_writes_nothing(project):
    make_old(project)
    before = (project / ".groundwork/spec-version").read_text()
    assert not upgrade(project, dry_run=True).up_to_date
    assert (project / ".groundwork/spec-version").read_text() == before
    upgrade(project)
    assert upgrade(project).up_to_date


def test_project_newer_than_tool_is_refused(project):
    (project / ".groundwork/spec-version").write_text("9.9\n")
    with pytest.raises(RuntimeError):
        upgrade(project)


def test_start_suggests_upgrade(project):
    make_old(project)
    assert "gw upgrade" in briefing(project, "alice", lang="en")


def test_changelog_window():
    lines = changelog_between("0.2", "0.3")
    assert any(l.startswith("## 0.3.0") for l in lines)
    assert not any(l.startswith("## 0.2.0") for l in lines)


def test_cli_upgrade(project, monkeypatch):
    make_old(project)
    monkeypatch.chdir(project)
    r = CliRunner().invoke(app, ["upgrade", "--dry-run"])
    assert r.exit_code == 0 and "would update" in r.output
    r = CliRunner().invoke(app, ["upgrade"])
    assert r.exit_code == 0 and "pull request" in r.output
    assert "already on spec" in CliRunner().invoke(app, ["upgrade"]).output


def test_patch_upgrade_refreshes_workflow(project):
    wf = project / ".github/workflows/groundwork.yml"
    wf.write_text("name: groundwork\n# old workflow without the status-race fix\n"
                  "run: pip install git+https://github.com/kevenzhuang/groundwork@v0.3.0\n")
    res = upgrade(project)
    assert ".github/workflows/groundwork.yml" in res.changed
    text = wf.read_text()
    assert "cancel-in-progress: true" in text and f"@v{__version__}" in text and "retrying" in text
