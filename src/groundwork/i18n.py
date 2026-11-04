"""Language selection and user-facing messages.

Resolution order (spec §0, principle: serve the user):
  1. explicit --lang
  2. GW_LANG environment variable
  3. `language` in .groundwork/config.yaml, unless it is `auto`
  4. auto: the language the record itself is written in (PROJECT.md, latest sessions)
  5. the system locale (LANG / LC_ALL)
  6. English

Record content is never translated: what people write is stored as written.
Add a language by adding a column to MESSAGES (and to site/status label tables);
missing keys fall back to English.
"""

from __future__ import annotations

import locale
import os
import re
from pathlib import Path

SUPPORTED = ("en", "zh")
_CJK = re.compile(r"[一-鿿]")


def normalize(code: str | None) -> str | None:
    if not code:
        return None
    c = code.strip().lower().replace("_", "-")
    if c.startswith("zh"):
        return "zh"
    if c.startswith("en"):
        return "en"
    return c.split("-")[0] if c.split("-")[0] in SUPPORTED else None


def detect_text(text: str, min_letters: int = 8) -> str | None:
    """Guess the language of record text. Returns None when there is too little signal."""
    text = re.sub(r"<!--.*?-->|`[^`]*`", "", text or "", flags=re.DOTALL)
    letters = sum(ch.isalpha() for ch in text)
    if letters < min_letters:
        return None
    cjk = len(_CJK.findall(text))
    return "zh" if cjk / max(letters, 1) > 0.15 else "en"


def _prose(text: str) -> str:
    """Only what people wrote: drop front-matter keys, fixed headings, tables, placeholders."""
    from .model import FrontMatterError, split_front_matter
    try:
        fm, body = split_front_matter(text)
    except FrontMatterError:
        fm, body = {}, text
    # The title is ignored on purpose: many people give English titles to projects they work on in
    # another language (e.g. a Chinese team with an English paper title).
    keep: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "|", "<!--", "_(blank)_")):
            continue
        keep.append(re.sub(r"^[-*]\s+(`[^`]*`\s*\([^)]*\):)?", "", s))
    return "\n".join(keep)


def _record_text(root: Path) -> str:
    parts = []
    p = root / "PROJECT.md"
    if p.is_file():
        parts.append(_prose(p.read_text(encoding="utf-8", errors="ignore")))
    s = root / "sessions"
    if s.is_dir():
        for f in sorted(s.glob("*.md"))[-3:]:
            parts.append(_prose(f.read_text(encoding="utf-8", errors="ignore")))
    return "\n".join(parts)


def system_language() -> str | None:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        lang = normalize(os.environ.get(var))
        if lang:
            return lang
    try:
        return normalize(locale.getlocale()[0])
    except (ValueError, TypeError):
        return None


def resolve(root: Path | None = None, explicit: str | None = None, config: dict | None = None) -> str:
    for cand in (explicit, os.environ.get("GW_LANG")):
        lang = normalize(cand)
        if lang in SUPPORTED:
            return lang
    if config is None and root is not None:
        from .project import load_config
        config = load_config(root)
    configured = normalize(str((config or {}).get("language") or "auto"))
    if configured in SUPPORTED:
        return configured
    if root is not None:
        lang = detect_text(_record_text(root))
        if lang:
            return lang
    return system_language() if system_language() in SUPPORTED else "en"


MESSAGES: dict[str, dict[str, str]] = {
    # init
    "init.done": {"en": "Initialized Groundwork project in {path}", "zh": "已在 {path} 初始化 Groundwork 项目"},
    "init.next": {"en": "Next: edit PROJECT.md, review ROLES.md and DECISION-RIGHTS.md, then run `gw check`.",
                  "zh": "下一步：填写 PROJECT.md，检查 ROLES.md 和 DECISION-RIGHTS.md，然后运行 `gw check`。"},
    "init.created": {"en": "  created {path}", "zh": "  已创建 {path}"},
    # note
    "note.ok": {"en": "noted → {path}", "zh": "已记录 → {path}"},
    "note.blocked_hint": {"en": "Rephrase without it, or write a placeholder like [withheld: credential; ask <id>].",
                          "zh": "请去掉该内容，或改用占位写法，例如 [withheld: credential; ask <id>]。"},
    # end
    "end.header": {"en": "Session for {who}", "zh": "{who} 的工作记录"},
    "end.since": {"en": " since {t}", "zh": "（自 {t} 起）"},
    "end.first": {"en": " (first session)", "zh": "（第一次收工）"},
    "end.summary": {"en": "  {c} changed file(s), {n} note(s), {a} agent transcript(s) to archive",
                    "zh": "  {c} 个文件有改动，{n} 条随手记，{a} 份 agent 日志待归档"},
    "end.why_one": {"en": "  Why did `{x}` change? (Enter to skip)", "zh": "  `{x}` 为什么改？（回车跳过）"},
    "end.why_many": {"en": "  Why did {n} files in `{x}` change? (Enter to skip)",
                     "zh": "  `{x}` 里的 {n} 个文件为什么改？（回车跳过）"},
    "end.q.did": {"en": "  What did you do? (one line is fine)", "zh": "  今天做了什么？（一句话即可）"},
    "end.q.thinking": {"en": "  What were you thinking or trying?", "zh": "  当时在想什么、尝试什么？"},
    "end.q.blocked": {"en": "  Anything blocked?", "zh": "  有什么卡住了吗？"},
    "end.q.next": {"en": "  What's next?", "zh": "  下一步做什么？"},
    "end.q.unverified": {"en": "  Anything you relied on that isn't verified yet?", "zh": "  有没有用到但还没核验的内容？"},
    "end.confirm": {"en": "Confirm this record as accurate?", "zh": "确认这份记录准确无误吗？"},
    "end.wrote": {"en": "wrote {path}", "zh": "已写入 {path}"},
    "end.missing": {"en": "  {n} change(s) without a reason: {files}", "zh": "  {n} 处改动没有填写原因：{files}"},
    "end.unconfirmed": {"en": "  Draft is unconfirmed. A human confirms it (set confirmed_by, or merge its pull request).",
                        "zh": "  草稿尚未确认，需由本人确认（填写 confirmed_by，或合并对应的 PR）。"},
    "end.next": {"en": "  Next: review, commit, and open a pull request.", "zh": "  下一步：检查、提交，并开一个 PR。"},
    "end.agent_confirm": {"en": "An agent cannot confirm a session (spec §5.2). Ask the human to confirm.",
                          "zh": "agent 不能确认工作记录（规范 §5.2），请由本人确认。"},
    "end.blocked_hint": {"en": "Remove it or use a placeholder like [withheld: credential; ask <id>].",
                         "zh": "请删除该内容，或改用占位写法，例如 [withheld: credential; ask <id>]。"},
    # start briefing
    "start.project": {"en": "Project: {title}  (stage: {stage})", "zh": "项目：{title}（阶段：{stage}）"},
    "start.last": {"en": "Last session: {date} by {who}", "zh": "上次工作：{date}，{who}"},
    "start.none": {"en": "No confirmed session yet. Say \"end\" (or run `gw end`) when you finish working.",
                   "zh": "还没有已确认的工作记录。结束工作时说\"收工\"（或运行 `gw end`）。"},
    "start.drafts": {"en": "⚠ {n} unconfirmed session draft(s): {files}", "zh": "⚠ {n} 份工作记录草稿待确认：{files}"},
    "start.upgrade": {"en": "ℹ This project follows spec {old}; your tool supports {new}. Run `gw upgrade` when convenient.",
                      "zh": "ℹ 本项目使用规范 {old}，你的工具已支持 {new}。方便时运行 `gw upgrade` 升级。"},
    "start.pending": {"en": "Waiting for a decision:", "zh": "待决定事项："},
    "start.questions": {"en": "Questions for you ({who}):", "zh": "需要你（{who}）回答的问题："},
    "start.verif": {"en": "Verification: {h}/{t} human-verified, {u} unverified, {d} disputed, {o} oral-only",
                    "zh": "核验：{h}/{t} 已人工核验，{u} 未核验，{d} 有争议，{o} 仅口述"},
    "start.unreadable": {"en": "⚠ Unreadable records (run `gw check`): {files}",
                         "zh": "⚠ 以下记录格式有误（请运行 `gw check`）：{files}"},
    "sec.Did": {"en": "Did", "zh": "完成"},
    "sec.Thinking": {"en": "Thinking", "zh": "思路"},
    "sec.Blocked": {"en": "Blocked", "zh": "卡点"},
    "sec.Next": {"en": "Next", "zh": "下一步"},
    "sec.Unverified items touched": {"en": "Unverified", "zh": "未核验"},
    # check
    "check.summary": {"en": "{e} error(s), {w} warning(s)", "zh": "{e} 个错误，{w} 个警告"},
    # status/site
    "site.wrote": {"en": "wrote {path}  ({aud}, {lng})", "zh": "已生成 {path}（{aud}，{lng}）"},
    "site.public": {"en": "Publishing a public view is a T3 decision (spec §12).",
                    "zh": "公开发布视图属于 T3 决策，需要先请示（规范 §12）。"},
    "status.wrote": {"en": "wrote {path}", "zh": "已生成 {path}"},
}


def t(key: str, lang: str, **kw) -> str:
    entry = MESSAGES.get(key, {})
    text = entry.get(lang) or entry.get("en") or key
    return text.format(**kw) if kw else text
