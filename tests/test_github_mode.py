import datetime as dt
import json

from conftest import commit, write
from typer.testing import CliRunner

from groundwork.approvals import approved_logins, verify
from groundwork.cli import app
from groundwork.status import briefing, render_status

NOW = dt.datetime(2026, 11, 4, 12, 0)

ROLES = """---
principals:
  - {id: alice, kind: human, roles: [owner, lead], git_identity: alice@example.org, github: alice-gh}
  - {id: bob, kind: human, roles: [advisor], git_identity: bob@example.org, github: "@Bob-GH"}
  - {id: carol, kind: human, roles: [contributor], git_identity: carol@example.org}
  - {id: claude-1, kind: agent, roles: [agent], sponsor: alice, git_identity: c@users.noreply.example}
---
"""


def dec(root, id, tier, status, extra):
    write(root, f"decisions/{id}-d.md", f'---\nid: "{id}"\ndate: 2026-11-04\ntitle: D{id}\ntier: {tier}\n'
          f"{extra}\nstatus: {status}\ncapture: contemporaneous\n---\n\n## Decision\n\nbody\n")
    return f"decisions/{id}-d.md"


# ---------------------------------------------------------------- init
def test_init_writes_workflow_verbatim(project):
    wf = (project / ".github/workflows/groundwork.yml").read_text()
    assert "${{ github.token }}" in wf and "gw approvals" in wf


def test_init_records_github_login(tmp_path):
    from groundwork.init import init_project
    init_project(tmp_path, "X", "alice", "Alice", "a@example.org", owner_github="@alice-gh", github_workflow=False)
    assert 'github: "alice-gh"' in (tmp_path / "ROLES.md").read_text()
    assert not (tmp_path / ".github").exists()


# ---------------------------------------------------------------- approvals
def test_latest_review_state_wins():
    reviews = [{"user": {"login": "Bob-GH"}, "state": "APPROVED"},
               {"user": {"login": "bob-gh"}, "state": "CHANGES_REQUESTED"},
               {"user": {"login": "x"}, "state": "COMMENTED"},
               {"user": {"login": "y"}, "state": "APPROVED"}]
    assert approved_logins(reviews) == {"y"}


def test_t3_requires_matching_github_review(project):
    write(project, "ROLES.md", ROLES)
    f = dec(project, "0002", "T3", "accepted", "decider: alice\napproved_by: bob")
    assert verify(project, [f], [], author="alice-gh")  # no review → problem
    ok = [{"user": {"login": "bob-gh"}, "state": "APPROVED"}]
    assert verify(project, [f], ok, author="alice-gh") == []


def test_author_counts_as_approver_for_own_pr(project):
    write(project, "ROLES.md", ROLES)
    f = dec(project, "0002", "T3", "accepted", "decider: alice\napproved_by: alice")
    assert verify(project, [f], [], author="alice-gh") == []
    assert verify(project, [f], [], author="someone-else")  # not author, no review


def test_approver_without_github_login_cannot_be_verified(project):
    write(project, "ROLES.md", ROLES)
    f = dec(project, "0002", "T3", "accepted", "decider: alice\napproved_by: carol")
    msgs = [i.message for i in verify(project, [f], [], author="alice-gh")]
    assert any("no `github` login" in m for m in msgs)


def test_proposals_and_t1_need_no_review(project):
    write(project, "ROLES.md", ROLES)
    a = dec(project, "0002", "T0", "proposed", "proposed_by: claude-1")
    b = dec(project, "0003", "T1", "accepted", "decider: alice")
    assert verify(project, [a, b, "paper/x.tex"], [], author="claude-bot") == []


def test_cli_approvals(project, monkeypatch, tmp_path):
    write(project, "ROLES.md", ROLES)
    f = dec(project, "0002", "T2", "accepted", "decider: alice\nnotified: [bob]\nveto_window: 3d\napproved_by: bob")
    (tmp_path / "r.json").write_text(json.dumps([]))
    (tmp_path / "c.txt").write_text(f + "\n")
    monkeypatch.chdir(project)
    args = ["approvals", "--reviews", str(tmp_path / "r.json"), "--changed", str(tmp_path / "c.txt"), "--author", "alice-gh"]
    assert CliRunner().invoke(app, args).exit_code == 1
    (tmp_path / "r.json").write_text(json.dumps([{"user": {"login": "BOB-GH"}, "state": "APPROVED"}]))
    assert CliRunner().invoke(app, args).exit_code == 0


# ---------------------------------------------------------------- status & start
def test_status_page(project):
    write(project, "ROLES.md", ROLES)
    dec(project, "0002", "T0", "proposed", "proposed_by: claude-1")
    dec(project, "0003", "T3", "accepted", "decider: alice\napproved_by: bob")
    write(project, "open-questions.md", "---\nquestions:\n  - {id: Q1, question: 'Valid?', asked_by: alice, routed_to: bob, date: 2026-11-01, status: open}\n---\n")
    s = render_status(project, now=NOW)
    assert "Waiting for a decision (1)" in s and "D0002" in s
    assert "**T3** accepted · D0003" in s and "approved by bob" in s
    assert "@Bob-GH" in s
    assert "Do not edit by hand" in s and "🟢" in s


def test_malformed_questions_file_is_reported_not_fatal(project):
    write(project, "open-questions.md", "---\nquestions:\n  - {id: Q1, question: Valid?, x: y}\n---\n")
    s = render_status(project, now=NOW)
    assert "open-questions.md" in s and "could not be read" in s


def test_status_zh_from_config(project):
    cfg = project / ".groundwork/config.yaml"
    cfg.write_text(cfg.read_text().replace("language: en", "language: zh"))
    assert "项目状态" in render_status(project, now=NOW)


def test_status_never_shows_restricted(project):
    write(project, "decisions/0009-x.md", '---\nid: "0009"\ndate: 2026-11-04\ntitle: SECRET-TITLE\ntier: T3\n'
          "decider: alice\napproved_by: alice\nstatus: accepted\ncapture: contemporaneous\nclassification: restricted\n---\n")
    s = render_status(project, now=NOW)
    assert "SECRET-TITLE" not in s and "withheld" in s


def test_briefing_after_session(project):
    from groundwork.capture import collect, write_session
    commit(project, "init")
    write(project, "a.py", "x\n")
    commit(project, "work")
    write_session(project, "alice", collect(project),
                  {"did": "wrote a.py", "blocked": "no data", "next": "get data"}, confirm=True, now=NOW)
    b = briefing(project, "alice", now=NOW)
    assert "Last session" in b and "no data" in b and "get data" in b


def test_cli_start_and_status(project, monkeypatch):
    monkeypatch.chdir(project)
    r = CliRunner().invoke(app, ["start", "--as", "alice"])
    assert r.exit_code == 0 and "No confirmed session yet" in r.output
    r = CliRunner().invoke(app, ["status"])
    assert r.exit_code == 0 and (project / "STATUS.md").is_file()
