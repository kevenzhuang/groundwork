from pathlib import Path

from conftest import ROLES_WITH_AGENT, TODAY, commit, write

from groundwork.check import run_check


def codes(root: Path, level: str | None = None) -> list[str]:
    return [i.code for i in run_check(root, today=TODAY) if level is None or i.level == level]


def test_fresh_project_has_no_errors(project):
    assert codes(project, "error") == []
    assert codes(project, "warning") == ["W01"]


def test_missing_required_file(project):
    (project / "AGENTS.md").unlink()
    assert "E01" in codes(project, "error")


def test_roles_need_exactly_one_owner_and_sponsored_agents(project):
    write(project, "ROLES.md", """---
principals:
  - {id: a, kind: human, roles: [owner]}
  - {id: b, kind: human, roles: [owner]}
  - {id: bot, kind: agent, roles: [agent]}
---
""")
    msgs = [i.message for i in run_check(project, today=TODAY) if i.code == "E02"]
    assert any("exactly one owner" in m for m in msgs)
    assert any("no sponsor" in m for m in msgs)


def test_agent_cannot_be_owner(project):
    write(project, "ROLES.md", """---
principals:
  - {id: bot, kind: agent, roles: [owner], sponsor: x}
---
""")
    assert "E02" in codes(project, "error")


DECISION = """---
id: "{id}"
date: 2026-11-04
title: Test
tier: {tier}
{extra}
status: {status}
capture: contemporaneous
---
body
"""


def add_decision(root, id="0002", tier="T1", status="accepted", extra="decider: alice"):
    return write(root, f"decisions/{id}-t.md", DECISION.format(id=id, tier=tier, status=status, extra=extra))


def test_agent_cannot_decide(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT)
    add_decision(project, extra="decider: claude-1")
    assert "E04" in codes(project, "error")


def test_t0_proposal_needs_proposer_and_cannot_be_accepted(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT)
    add_decision(project, tier="T0", status="accepted", extra="")
    msgs = [i.message for i in run_check(project, today=TODAY) if i.code == "E03"]
    assert any("proposed_by" in m for m in msgs)
    assert any("cannot be `accepted`" in m for m in msgs)


def test_t0_proposal_ok(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT)
    add_decision(project, tier="T0", status="proposed", extra="proposed_by: claude-1")
    assert codes(project, "error") == []


def test_t2_requires_notice_and_window(project):
    add_decision(project, tier="T2")
    assert codes(project, "error").count("E03") == 2


def test_t3_requires_human_approval(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT)
    add_decision(project, tier="T3")
    assert "E03" in codes(project, "error")
    add_decision(project, id="0003", tier="T3", extra="decider: alice\napproved_by: claude-1")
    assert "E04" in codes(project, "error")


def test_invalid_enum(project):
    add_decision(project, status="maybe")
    assert "E10" in codes(project, "error")


LEDGER_HEAD = "id,status,provenance,verified_by,verified_on,method,evidence,classification,notes\n"


def test_human_verified_needs_who_when_how(project):
    write(project, "ledger/items.csv", LEDGER_HEAD + "S1,human-verified,agent:claude-1,,,,,internal,\n")
    assert codes(project, "error").count("E05") == 3


def test_agent_cannot_verify(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT)
    write(project, "ledger/items.csv",
          LEDGER_HEAD + "S1,human-verified,agent:claude-1,claude-1,2026-11-04,read source,url:https://x.org,internal,\n")
    assert "E06" in codes(project, "error")


def test_ledger_ok_row(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT)
    write(project, "ledger/items.csv",
          LEDGER_HEAD + "S1,human-verified,agent:claude-1,bob,2026-11-04,read source,url:https://x.org,internal,\n")
    assert codes(project, "error") == []


def test_ledger_missing_columns(project):
    write(project, "ledger/items.csv", "id,status\nS1,unverified\n")
    assert "E10" in codes(project, "error")


def test_secret_detected(project):
    write(project, "notes/2026-11-04.md", "- 10:00 [alice] server password: hunter2xyz\n")
    assert "E07" in codes(project, "error")


def test_blocklist_detected(project):
    cfg = project / ".groundwork/config.yaml"
    cfg.write_text(cfg.read_text().replace("blocklist: []", "blocklist: [ProjectNightjar]"))
    write(project, "PROJECT.md", (project / "PROJECT.md").read_text() + "\nfor projectnightjar\n")
    assert "E08" in codes(project, "error")


def test_private_ip_and_email_warn(project):
    write(project, "notes/x.md", "ssh 192.168.1.20 and mail bob@uni.edu\n")
    assert codes(project, "warning").count("W05") == 2


def test_accepted_decision_is_frozen(project):
    p = add_decision(project)
    commit(project, "accept 0002")
    p.write_text(p.read_text().replace("body", "rewritten body"))
    assert "E09" in codes(project, "error")


def test_superseding_is_allowed(project):
    p = add_decision(project)
    commit(project, "accept 0002")
    p.write_text(p.read_text().replace("status: accepted", "status: superseded"))
    add_decision(project, id="0003", extra="decider: alice\nsupersedes: \"0002\"")
    assert codes(project, "error") == []


def test_supersedes_unknown(project):
    add_decision(project, id="0003", extra="decider: alice\nsupersedes: \"0099\"")
    assert "E03" in codes(project, "error")


def test_old_open_question_warns(project):
    write(project, "open-questions.md", """---
questions:
  - {id: Q1, question: why, asked_by: alice, routed_to: alice, date: 2026-09-01, status: open}
---
""")
    assert "W02" in codes(project, "warning")


def test_unconfirmed_session_warns(project):
    write(project, "sessions/2026-11-04-alice.md", "---\nprincipal: alice\ncapture: contemporaneous\n---\n")
    assert "W04" in codes(project, "warning")
