from conftest import TODAY, write
from typer.testing import CliRunner

from groundwork.approvals import verify
from groundwork.check import run_check
from groundwork.cli import app
from groundwork.init import init_project
from groundwork.model import parse_roster, read_front_matter

BASE = """---
principals:
  - {id: gp-li, name: GP Li, kind: human, roles: [owner], github: gpli-gh}
  - {id: keven, name: Keven, kind: human, roles: [lead], github: keven-gh}
---
"""
# PR head where Keven makes himself owner
HIJACK = """---
principals:
  - {id: gp-li, name: GP Li, kind: human, roles: [advisor], github: gpli-gh}
  - {id: keven, name: Keven, kind: human, roles: [owner, lead], github: keven-gh}
---
"""
APPROVED_BY_PI = [{"user": {"login": "gpli-gh"}, "state": "APPROVED"}]


def test_roles_change_needs_owner_approval(project):
    write(project, "ROLES.md", BASE.replace("roles: [lead]", "roles: [lead, contributor]"))
    assert verify(project, ["ROLES.md"], [], author="keven-gh", base_roles=BASE)
    assert verify(project, ["ROLES.md"], APPROVED_BY_PI, author="keven-gh", base_roles=BASE) == []


def test_cannot_make_yourself_owner_and_self_approve(project):
    write(project, "ROLES.md", HIJACK)
    # Without the base, the head roster would say keven is owner and author == owner: must not pass.
    issues = verify(project, ["ROLES.md"], [], author="keven-gh", base_roles=BASE)
    assert issues and "gp-li" in issues[0].message


def test_cannot_swap_approvers_github_login_in_same_pr(project):
    write(project, "ROLES.md", BASE.replace("github: gpli-gh", "github: keven-gh"))
    write(project, "decisions/0002-v.md", '---\nid: "0002"\ndate: 2026-11-04\ntitle: Venue\ntier: T3\n'
          "decider: keven\napproved_by: gp-li\nstatus: accepted\ncapture: contemporaneous\n---\n")
    issues = verify(project, ["ROLES.md", "decisions/0002-v.md"], [], author="keven-gh", base_roles=BASE)
    msgs = " ".join(i.message for i in issues)
    assert "@gpli-gh" in msgs  # still checked against the real login from the base


def test_decision_rights_change_needs_owner(project):
    write(project, "ROLES.md", BASE)
    assert verify(project, ["DECISION-RIGHTS.md"], [], author="keven-gh", base_roles=BASE)


def test_initial_setup_pr_owner_approves(project):
    write(project, "ROLES.md", BASE)  # no base: file is new in this PR
    assert verify(project, ["ROLES.md"], [], author="keven-gh", base_roles=None)
    assert verify(project, ["ROLES.md"], APPROVED_BY_PI, author="keven-gh", base_roles=None) == []


def test_init_lead_sets_up_for_pi(tmp_path):
    init_project(tmp_path, "Edge Study", "gp-li", "GP Li", owner_github="gpli-gh",
                 lead_id="keven", lead_name="庄子钧", lead_github="keven-gh", lead_git="k@example.org",
                 github_workflow=False)
    roster, problems = parse_roster(read_front_matter(tmp_path / "ROLES.md")[0])
    assert problems == []
    assert roster.get("gp-li").roles == ["owner"] and roster.get("keven").roles == ["lead"]
    adopt, _ = read_front_matter(tmp_path / "decisions/0001-adopt-groundwork.md")
    assert adopt["tier"] == "T3" and adopt["decider"] == "keven" and adopt["approved_by"] == "gp-li"
    assert [i.code for i in run_check(tmp_path, today=TODAY) if i.level == "error"] == []


def test_init_single_person_still_works(tmp_path):
    init_project(tmp_path, "Solo", "keven", "Keven", github_workflow=False)
    roster, _ = parse_roster(read_front_matter(tmp_path / "ROLES.md")[0])
    assert roster.get("keven").roles == ["owner", "lead"]


def test_cli_init_with_lead(tmp_path):
    r = CliRunner().invoke(app, ["init", str(tmp_path), "-t", "Edge", "--owner", "gp-li", "--owner-name", "GP Li",
                                 "--github", "gpli-gh", "--lead", "keven", "--lead-name", "Keven",
                                 "--lead-github", "keven-gh", "--no-workflow"])
    assert r.exit_code == 0, r.output
    assert "id: keven" in (tmp_path / "ROLES.md").read_text()
    r = CliRunner().invoke(app, ["init", str(tmp_path / "b"), "-t", "E", "--owner", "gp-li", "--lead", "Keven Z"])
    assert r.exit_code == 2
