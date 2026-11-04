import datetime as dt

import pytest
from conftest import write
from typer.testing import CliRunner

from groundwork.cli import app
from groundwork.site import TemplateViolation, build, extract, md, render, validate_rendered

NOW = dt.datetime(2026, 11, 4, 12, 0)
HEAD = "id,status,provenance,verified_by,verified_on,method,evidence,classification,notes\n"


def decision(root, id, tier="T1", status="accepted", title="t", extra="decider: alice", cls="internal"):
    write(root, f"decisions/{id}-x.md", f"""---
id: "{id}"
date: 2026-11-04
title: {title}
tier: {tier}
{extra}
status: {status}
capture: contemporaneous
classification: {cls}
---

## Decision

Decision body {id}.

## Reasons

Because {id}.
""")


@pytest.fixture
def rich(project):
    write(project, "ledger/items.csv", HEAD
          + "S1,human-verified,agent:c,alice,2026-11-04,read,url:https://x.org,internal,\n"
          + "S2,unverified,agent:c,,,,,internal,\n"
          + "S3,unverified,agent:c,,,,url:https://y.org,restricted,secret thing\n"
          + "S4,auto-checked,tool:refchecker,,,,url:https://z.org,public,\n")
    decision(project, "0002", "T3", extra="decider: alice\napproved_by: alice", title="Target venue")
    decision(project, "0003", "T0", "proposed", title="Switch model", extra="proposed_by: claude-1")
    decision(project, "0004", "T1", title="Hidden one", cls="restricted")
    return project


def page(root, audience="receiver", lang="en"):
    return render(root, extract(root, audience, now=NOW), lang)


def test_restricted_items_never_rendered(rich):
    d = extract(rich, "receiver", now=NOW)
    assert d["meta"]["hidden_items"] == 2
    p = page(rich)
    assert "secret thing" not in p and "Hidden one" not in p
    assert "2 items withheld" in p


def test_verification_counts_and_oral_only(rich):
    v = extract(rich, "receiver", now=NOW)["verification"]
    assert v["counts"]["human-verified"] == 1 and v["counts"]["unverified"] == 1
    assert v["oral_only"] == 1 and v["total"] == 3


def test_public_view_shows_only_public(rich):
    d = extract(rich, "public", now=NOW)
    assert [r["id"] for r in d["ledger"]] == ["S4"]
    assert d["decisions"] == []


def test_owner_view_shows_pending_and_t2_t3_only(rich):
    p = page(rich, "owner")
    assert "Waiting for a decision" in p and "Switch model" in p
    assert "Target venue" in p
    assert "Adopt Groundwork" not in p  # T1 decision 0001 hidden from owner


def test_mandatory_elements_present_in_all_views(rich):
    for a in ("owner", "advisor", "receiver", "public"):
        for lang in ("en", "zh"):
            assert validate_rendered(page(rich, a, lang)) == []


def test_zh_labels(rich):
    p = page(rich, "advisor", "zh")
    assert "核验状态" in p and "人工核验" in p and 'lang="zh-CN"' in p


def test_record_content_cannot_inject_html(project):
    write(project, "PROJECT.md", "---\ntitle: '<script>alert(1)</script>'\n---\n\n## Goal\n\n<img src=x onerror=alert(1)> **bold**\n")
    p = page(project)
    assert "<script>alert(1)" not in p and "<img src=x" not in p
    assert "&lt;img" in p and "<strong>bold</strong>" in p


def test_custom_template_must_keep_required_elements(rich):
    write(rich, ".groundwork/site/template.html.j2", "<html><body data-gw=\"header\">{{ d.meta.audience }}</body></html>")
    with pytest.raises(TemplateViolation):
        page(rich)


def test_custom_template_allowed_when_complete(rich):
    write(rich, ".groundwork/site/template.html.j2",
          '<div data-gw="header"></div><div data-gw="badge-legend"></div>'
          '<div data-gw="decision-tier"></div><div data-gw="footer">{{ d.meta.tool }}</div>')
    assert "groundwork-lab" in page(rich)


def test_no_python_reprs_leak_into_page(rich):
    for a in ("owner", "advisor", "receiver"):
        for lang in ("en", "zh"):
            p = page(rich, a, lang)
            assert "built-in method" not in p and "object at 0x" not in p


def test_unreadable_record_is_announced_not_silently_dropped(rich):
    write(rich, "decisions/0009-bad.md", "---\ntitle: Venue: X\n---\n")
    p = page(rich, "owner")
    assert "could not be read" in p and "decisions/0009-bad.md" in p


def test_problem_items_listed_before_verified(rich):
    ids = [r["id"] for r in extract(rich, "receiver", now=NOW)["ledger"]]
    assert ids.index("S2") < ids.index("S1")


def test_md_tables_and_lists():
    h = str(md("| a | b |\n|---|---|\n| 1 | 2 |\n\n- x\n- y\n\n## H"))
    assert "<table>" in h and "<td>1</td>" in h and "<li>x</li>" in h and "<h3>H</h3>" in h


def test_build_and_cli(rich, monkeypatch):
    out = build(rich, "advisor", "en", now=NOW)
    assert out.name == "advisor.html" and out.read_text().startswith("<!DOCTYPE html>")
    monkeypatch.chdir(rich)
    r = CliRunner().invoke(app, ["site", "--all", "--lang", "zh"])
    assert r.exit_code == 0, r.output
    assert {p.name for p in (rich / ".groundwork/build").glob("*.html")} >= {"owner.html", "advisor.html", "receiver.html"}
