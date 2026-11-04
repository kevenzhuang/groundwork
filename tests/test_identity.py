from conftest import ROLES_WITH_AGENT, TODAY, write
from typer.testing import CliRunner

from groundwork.check import run_check
from groundwork.cli import app
from groundwork.model import parse_roster, split_front_matter


def issues(root, code):
    return [i for i in run_check(root, today=TODAY) if i.code == code]


def roster_of(text):
    return parse_roster(split_front_matter(text)[0])


def test_id_format_enforced_with_suggestion(project):
    write(project, "ROLES.md", """---
principals:
  - {id: Keven Zhuang, name: Keven, kind: human, roles: [owner]}
---
""")
    msgs = [i.message for i in issues(project, "E12")]
    assert any("keven-zhuang" in m for m in msgs)


def test_chinese_id_rejected_but_chinese_name_fine(project):
    write(project, "ROLES.md", """---
principals:
  - {id: 庄子钧, name: 庄子钧, kind: human, roles: [owner]}
---
""")
    assert issues(project, "E12")
    write(project, "ROLES.md", """---
principals:
  - {id: alice, name: 庄子钧, aliases: [Keven, 子钧], kind: human, roles: [owner]}
---
""")
    assert not issues(project, "E12") and not issues(project, "E02")


def test_duplicate_ids_case_insensitive():
    _, problems = roster_of("""---
principals:
  - {id: keven, name: A, kind: human, roles: [owner]}
  - {id: Keven, name: B, kind: human, roles: [lead]}
---
""")
    assert any("duplicate" in p for p in problems)


def test_name_required():
    _, problems = roster_of("---\nprincipals:\n  - {id: keven, kind: human, roles: [owner]}\n---\n")
    assert any("`name` is required" in p for p in problems)


def test_github_and_orcid_formats():
    _, problems = roster_of("""---
principals:
  - {id: keven, name: K, kind: human, roles: [owner], github: "bad login!", orcid: "1234"}
---
""")
    assert sum("[E12]" in p for p in problems) == 2
    _, ok = roster_of("""---
principals:
  - {id: keven, name: K, kind: human, roles: [owner], github: "@keven-z", orcid: "https://orcid.org/0000-0002-1825-009X"}
---
""")
    assert ok == []


def test_unknown_reference_with_hint(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT.replace("name: Bob", "name: Bob Li\n    aliases: [王老师]"))
    write(project, "open-questions.md", """---
questions:
  - {id: Q1, question: x, asked_by: alice, routed_to: 王老师, date: 2026-11-01, status: open}
---
""")
    msgs = [i.message for i in issues(project, "E12")]
    assert any("unknown principal `王老师`" in m and "did you mean `bob`" in m for m in msgs)


def test_display_name_in_decision_is_flagged(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT)
    write(project, "decisions/0002-x.md", """---
id: "0002"
date: 2026-11-04
title: t
tier: T1
decider: Alice
status: accepted
capture: contemporaneous
---
""")
    msgs = [i.message for i in issues(project, "E12")]
    assert any("`Alice`" in m and "did you mean `alice`" in m for m in msgs)


def test_note_author_must_be_known(project):
    write(project, "ROLES.md", ROLES_WITH_AGENT)
    write(project, "notes/2026-11-04.md", "# Notes\n\n- 10:00 [mallory] hi\n")
    assert issues(project, "E12")


def test_resolve_by_alias_name_and_github():
    roster, _ = roster_of("""---
principals:
  - {id: arnold-wang, name: Shuoyu Wang, aliases: [Arnold, 王老师], github: arnold-gh, kind: human, roles: [advisor]}
  - {id: keven, name: Keven Zhuang, kind: human, roles: [owner]}
---
""")
    for q in ("Arnold", "王老师", "@arnold-gh", "wang", "arnold-wang"):
        assert [p.id for p in roster.resolve(q)] == ["arnold-wang"], q
    assert roster.resolve("nobody") == []


def test_cli_who(project, monkeypatch):
    write(project, "ROLES.md", ROLES_WITH_AGENT.replace("name: Bob", "name: Bob Li\n    aliases: [王老师]"))
    monkeypatch.chdir(project)
    r = CliRunner().invoke(app, ["who", "王老师"])
    assert r.exit_code == 0 and "bob" in r.output
    assert CliRunner().invoke(app, ["who", "nobody"]).exit_code == 1
