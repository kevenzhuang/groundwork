import datetime as dt

import pytest
from conftest import write
from typer.testing import CliRunner

from groundwork import i18n
from groundwork.cli import app
from groundwork.init import init_project
from groundwork.status import briefing, render_status

NOW = dt.datetime(2026, 11, 4, 12, 0)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in ("GW_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("LANG", "C")  # no locale signal unless a test sets one


def test_detect_text():
    assert i18n.detect_text("我们在做边缘数据中心的冷却改造研究") == "zh"
    assert i18n.detect_text("We study cooling retrofits for edge data centers") == "en"
    assert i18n.detect_text("ok") is None


def test_normalize():
    assert i18n.normalize("zh_CN.UTF-8") == "zh"
    assert i18n.normalize("en-US") == "en"
    assert i18n.normalize("fr_FR") is None


def test_chinese_record_gives_chinese_output(project):
    write(project, "PROJECT.md", "---\ntitle: 边缘机房冷却改造\nstage: write\n---\n\n## Goal\n\n找出回本最快的冷却改造方案。\n")
    assert i18n.resolve(project) == "zh"
    assert "项目状态" in render_status(project, now=NOW)
    assert "项目：边缘机房冷却改造" in briefing(project, "alice", now=NOW)


def test_english_record_gives_english_output(project):
    write(project, "PROJECT.md", "---\ntitle: Edge cooling\nstage: write\n---\n\n## Goal\n\nFind which retrofits pay back fastest.\n")
    assert i18n.resolve(project) == "en"
    assert "Project status" in render_status(project, now=NOW)


def test_english_title_with_chinese_content_is_chinese(project):
    write(project, "PROJECT.md", "---\ntitle: DC-S26 Edge Cooling\n---\n\n## Goal\n\n找出回本最快的冷却改造方案。\n")
    assert i18n.resolve(project) == "zh"


def test_fixed_english_headings_do_not_count(project):
    # a fresh template has English headings and placeholders only: no signal → system locale
    assert i18n.resolve(project) == "en"


def test_system_locale_used_when_record_is_empty(project, monkeypatch):
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert i18n.resolve(project) == "zh"


def test_priority_explicit_then_env_then_config(project, monkeypatch):
    write(project, "PROJECT.md", "---\ntitle: 边缘机房冷却改造\n---\n\n## Goal\n\n找出回本最快的方案。\n")
    cfg = project / ".groundwork/config.yaml"
    cfg.write_text(cfg.read_text().replace("language: auto", "language: en"))
    assert i18n.resolve(project) == "en"            # config beats record
    monkeypatch.setenv("GW_LANG", "zh")
    assert i18n.resolve(project) == "zh"            # env beats config
    assert i18n.resolve(project, "en") == "en"      # explicit beats env


def test_missing_translation_falls_back_to_english():
    assert i18n.t("check.summary", "fr", e=1, w=2) == "1 error(s), 2 warning(s)"


def test_init_with_chinese_title_speaks_chinese(tmp_path):
    r = CliRunner().invoke(app, ["init", str(tmp_path), "-t", "边缘机房冷却改造", "--owner", "keven", "--no-workflow"])
    assert r.exit_code == 0 and "已在" in r.output
    assert "language: auto" in (tmp_path / ".groundwork/config.yaml").read_text()


def test_explicit_lang_is_saved_in_config(tmp_path):
    r = CliRunner().invoke(app, ["--lang", "zh", "init", str(tmp_path), "-t", "Edge", "--owner", "k", "--no-workflow"])
    assert r.exit_code == 0
    assert "language: zh" in (tmp_path / ".groundwork/config.yaml").read_text()


def test_end_prompts_follow_language_and_answers_are_not_translated(project, monkeypatch):
    from conftest import commit
    write(project, "PROJECT.md", "---\ntitle: 冷却研究\n---\n\n## Goal\n\n找出回本最快的冷却改造方案。\n")
    commit(project, "init")
    write(project, "a.py", "x\n")
    commit(project, "work")
    monkeypatch.chdir(project)
    r = CliRunner().invoke(app, ["end", "--as", "alice"], input="写了基线脚本\nfinished baseline\n\n\n\n\ny\n")
    assert r.exit_code == 0, r.output
    assert "为什么改" in r.output and "今天做了什么" in r.output
    body = next((project / "sessions").glob("*.md")).read_text()
    assert "写了基线脚本" in body and "finished baseline" in body  # stored exactly as written


def test_per_command_lang_flag(project, monkeypatch):
    monkeypatch.chdir(project)
    r = CliRunner().invoke(app, ["start", "--as", "alice", "--lang", "zh"])
    assert "还没有已确认的工作记录" in r.output
