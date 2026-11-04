import datetime as dt

import pytest
from conftest import TODAY
from typer.testing import CliRunner

from groundwork.cli import app
from groundwork.init import init_project
from groundwork.note import BlockedNote, add_note


def test_init_does_not_overwrite(project):
    (project / "PROJECT.md").write_text("mine")
    init_project(project, "Other", "alice", "Alice", today=TODAY)
    assert (project / "PROJECT.md").read_text() == "mine"


def test_init_renders_templates(project):
    text = (project / "decisions/0001-adopt-groundwork.md").read_text()
    assert "decider: alice" in text and "{{" not in text
    assert (project / ".groundwork/SPEC.md").read_text().startswith("# Groundwork Specification")


def test_note_appends(project):
    now = dt.datetime(2026, 11, 4, 9, 30)
    p = add_note(project, "alice", "dropped section 3,  duplicate of 2", now=now)
    add_note(project, "alice", "second", now=now.replace(minute=45))
    lines = p.read_text().splitlines()
    assert lines[-2] == "- 09:30 [alice] dropped section 3, duplicate of 2"
    assert lines[-1].endswith("second")


def test_note_blocks_secrets_even_when_allowed(project):
    with pytest.raises(BlockedNote):
        add_note(project, "alice", "token: ghp_" + "a" * 36, allow_flagged=True)


def test_note_flags_email_unless_allowed(project):
    with pytest.raises(BlockedNote):
        add_note(project, "alice", "ask carol@uni.edu")
    add_note(project, "alice", "ask carol@uni.edu", allow_flagged=True)


def test_cli_check_exit_codes(project, monkeypatch):
    monkeypatch.chdir(project)
    runner = CliRunner()
    assert runner.invoke(app, ["check"]).exit_code == 0
    assert runner.invoke(app, ["check", "--strict"]).exit_code == 1  # W01
    (project / "AGENTS.md").unlink()
    r = runner.invoke(app, ["check", "--json"])
    assert r.exit_code == 1 and '"E01"' in r.output


def test_cli_outside_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(app, ["check"])
    assert r.exit_code == 2
