import datetime as dt

import pytest
import yaml
from conftest import ROLES_WITH_AGENT, TODAY, commit, write
from typer.testing import CliRunner

from groundwork.capture import Blocked, collect, write_session
from groundwork.check import run_check
from groundwork.cli import app
from groundwork.model import read_front_matter

T0 = dt.datetime(2026, 11, 4, 10, 0)


@pytest.fixture
def started(project, tmp_path_factory, monkeypatch):
    """A project with one commit of real work, an agent log dir, and a temp archive."""
    commit(project, "init")
    write(project, "paper/intro.tex", "intro v1\n")
    commit(project, "draft intro")
    logs = tmp_path_factory.mktemp("claude")
    monkeypatch.setenv("GW_CLAUDE_DIR", str(logs))
    cfg = project / ".groundwork/config.yaml"
    cfg.write_text(cfg.read_text().replace("archive_agent_logs: false", "archive_agent_logs: true"))
    return project, logs, project / ".groundwork" / "archive"


def test_first_session_collects_history_and_skips_record_files(started):
    root, _, _ = started
    col = collect(root)
    paths = {c.path for c in col.changes}
    assert "paper/intro.tex" in paths
    assert not any(p.startswith(("sessions/", "notes/", ".groundwork/")) for p in paths)
    assert paths == {"paper/intro.tex"}  # scaffolding from `gw init` is not asked about
    assert col.base and col.head and col.base != col.head


def test_many_changes_are_grouped_by_directory():
    from groundwork.capture import Change, group_changes
    many = [Change("M", f"paper/s{i}.tex") for i in range(9)] + [Change("A", "run.py")]
    g = group_changes(many)
    assert set(g) == {"paper/", "run.py"} and len(g["paper/"]) == 9


def test_session_written_confirmed_and_next_starts_from_head(started):
    root, _, _ = started
    col = collect(root)
    p = write_session(root, "alice", col, {"did": "wrote intro", "reasons": {"paper/intro.tex": "first draft"}},
                      confirm=True, now=T0)
    fm, body = read_front_matter(p)
    assert fm["confirmed_by"] == "alice" and fm["head"] == col.head
    assert "`paper/intro.tex` (added): first draft" in body
    commit(root, "session 1")

    write(root, "paper/intro.tex", "intro v2\n")
    write(root, "analysis.py", "x = 1\n")
    commit(root, "revise")
    col2 = collect(root)
    assert col2.base == col.head
    assert {c.path for c in col2.changes} == {"paper/intro.tex", "analysis.py"}


def test_uncommitted_changes_are_included(started):
    root, _, _ = started
    write(root, "scratch.md", "idea\n")
    assert any(c.path == "scratch.md" and not c.committed for c in collect(root).changes)


def test_notes_since_last_session(started):
    root, _, _ = started
    write(root, "notes/2026-11-04.md", "# Notes\n\n- 09:00 [alice] before\n- 11:30 [alice] after\n")
    write_session(root, "alice", collect(root), {}, confirm=True, now=T0)
    texts = [n.text for n in collect(root).notes]
    assert texts == ["after"]


def test_agent_logs_archived_with_hash(started):
    root, logs, arch = started
    from groundwork.capture import claude_log_dir
    d = claude_log_dir(root)
    d.mkdir(parents=True)
    (d / "s1.jsonl").write_text('{"type":"user"}\n')
    p = write_session(root, "alice", collect(root), {}, confirm=True, now=T0)
    fm, _ = read_front_matter(p)
    ptr = [s for s in fm["sources"] if s.startswith("archive:")]
    assert len(ptr) == 1 and "@sha256:" in ptr[0]
    assert list(arch.rglob("s1.jsonl"))


def test_archive_off_by_default(project, monkeypatch, tmp_path):
    monkeypatch.setenv("GW_CLAUDE_DIR", str(tmp_path / "c"))
    from groundwork.capture import claude_log_dir
    commit(project, "init")
    d = claude_log_dir(project); d.mkdir(parents=True); (d / "s.jsonl").write_text("{}\n")
    assert collect(project).agent_logs == []


def test_secret_in_answers_blocks_write(started):
    root, _, _ = started
    with pytest.raises(Blocked):
        write_session(root, "alice", collect(root), {"did": "set password: hunter2xyz"}, confirm=True, now=T0)
    assert not list((root / "sessions").glob("*.md"))


def test_unconfirmed_draft_is_reused_same_day(started):
    root, _, _ = started
    a = write_session(root, "alice", collect(root), {}, confirm=False, now=T0)
    b = write_session(root, "alice", collect(root), {"did": "x"}, confirm=False, now=T0)
    assert a == b


def test_confirmed_session_then_check_clean(started):
    root, _, _ = started
    write_session(root, "alice", collect(root), {"did": "x"}, confirm=True, now=T0)
    assert [i.code for i in run_check(root, today=TODAY) if i.level == "error"] == []


def test_cli_end_with_answers_file(started, monkeypatch):
    root, _, _ = started
    monkeypatch.chdir(root)
    ans = root.parent / "answers.yaml"
    ans.write_text(yaml.safe_dump({"did": "drafted intro", "reasons": {"paper/intro.tex": "start paper"}}))
    r = CliRunner().invoke(app, ["end", "--as", "alice", "--answers", str(ans), "--confirm"])
    assert r.exit_code == 0, r.output
    s = next((root / "sessions").glob("*.md"))
    assert "start paper" in s.read_text()


def test_cli_end_interactive(started, monkeypatch):
    root, _, _ = started
    monkeypatch.chdir(root)
    # reason for intro.tex, then did/thinking/blocked/next/unverified, then confirm
    r = CliRunner().invoke(app, ["end", "--as", "alice"],
                           input="first draft\nwrote intro\ntrying a framing\n\nresults\n\ny\n")
    assert r.exit_code == 0, r.output
    fm, body = read_front_matter(next((root / "sessions").glob("*.md")))
    assert fm["confirmed_by"] == "alice"
    assert "first draft" in body and "trying a framing" in body


def test_cli_agent_cannot_confirm(started, monkeypatch):
    root, _, _ = started
    write(root, "ROLES.md", ROLES_WITH_AGENT)
    monkeypatch.chdir(root)
    r = CliRunner().invoke(app, ["end", "--as", "claude-1", "--draft", "--confirm"])
    assert r.exit_code == 1
    r = CliRunner().invoke(app, ["end", "--as", "claude-1", "--draft"])
    assert r.exit_code == 0
    fm, _ = read_front_matter(next((root / "sessions").glob("*.md")))
    assert fm["confirmed_by"] is None


def test_cli_preview_writes_nothing(started, monkeypatch):
    root, _, _ = started
    monkeypatch.chdir(root)
    r = CliRunner().invoke(app, ["end", "--preview"])
    assert r.exit_code == 0 and "paper/intro.tex" in r.output
    assert not list((root / "sessions").glob("*.md"))
