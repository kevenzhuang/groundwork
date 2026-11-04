"""`gw site`: per-audience, read-only views of the record (spec §12).

Two steps: extract (scope + classification applied) → render (template).
Rendering never changes meaning: mandatory elements are validated after rendering.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import re
from collections import Counter
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, select_autoescape
from markupsafe import Markup

from . import SPEC_VERSION, __version__, gitutil
from .model import FrontMatterError, read_front_matter

AUDIENCES = ("owner", "advisor", "receiver", "public")
VISIBLE = {  # classification levels each audience may see (restricted/secret never rendered)
    "owner": {"public", "internal"},
    "advisor": {"public", "internal"},
    "receiver": {"public", "internal"},
    "public": {"public"},
}
STATUS_ORDER = ["human-verified", "auto-checked", "unverified", "disputed", "retracted"]
REQUIRED_MARKERS = ["header", "badge-legend", "decision-tier", "footer"]


class TemplateViolation(RuntimeError):
    pass


# ------------------------------------------------------------- markdown (tiny, escaped)
_INLINE = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![*\w])\*([^*]+)\*(?!\*)"), r"<em>\1</em>"),
    (re.compile(r"(?<![\w])_([^_]+)_(?![\w])"), r"<em>\1</em>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"), r'<a href="\2">\1</a>'),
]


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    for pat, rep in _INLINE:
        s = pat.sub(rep, s)
    return s


def md(text: str) -> Markup:
    """Minimal Markdown → HTML: headings, lists, tables, paragraphs, inline code/bold/links.
    Input is escaped first, so record content can never inject HTML."""
    text = re.sub(r"<!--.*?-->", "", text or "", flags=re.DOTALL)
    out: list[str] = []
    para: list[str] = []
    in_list = False
    table: list[list[str]] = []

    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + " ".join(_inline(x) for x in para) + "</p>")
            para = []

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def flush_table():
        nonlocal table
        if table:
            rows = [r for r in table if not all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in r)]
            if rows:
                head, *body = rows
                out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head)
                           + "</tr></thead><tbody>"
                           + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                                     for r in body) + "</tbody></table>")
            table = []

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            continue
        if line.startswith("|") and line.endswith("|"):
            flush_para(); flush_list()
            table.append([c.strip() for c in line.strip("|").split("|")])
            continue
        flush_table()
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush_para(); flush_list()
            level = min(len(m.group(1)) + 1, 6)  # page owns h1
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
        elif re.match(r"^\s*[-*]\s+", line):
            flush_para()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append("<li>" + _inline(re.sub(r"^\s*[-*]\s+", "", line)) + "</li>")
        elif not line.strip():
            flush_para(); flush_list()
        else:
            flush_list()
            para.append(line.strip())
    flush_para(); flush_list(); flush_table()
    return Markup("\n".join(out))


def sections(body: str) -> dict[str, str]:
    """Split a markdown body on '## ' headings."""
    out: dict[str, str] = {}
    cur = None
    buf: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur, buf = line[3:].strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


# ------------------------------------------------------------- extract
def _visible(cls: Any, audience: str) -> bool:
    return str(cls or "internal") in VISIBLE[audience]


def _records(root: Path, folder: str, audience: str, bad: list[str] | None = None) -> tuple[list[dict], int]:
    d = root / folder
    items, hidden = [], 0
    if not d.is_dir():
        return items, hidden
    for p in sorted(d.glob("*.md")):
        try:
            fm, body = read_front_matter(p)
        except FrontMatterError:
            if bad is not None:
                bad.append(f"{folder}/{p.name}")
            continue
        if not _visible(fm.get("classification"), audience):
            hidden += 1
            continue
        items.append({"fm": fm, "body": body, "sections": sections(body), "file": p.name})
    return items, hidden


def extract(root: Path, audience: str = "receiver", now: dt.datetime | None = None,
            stale_days: int = 7) -> dict[str, Any]:
    if audience not in AUDIENCES:
        raise ValueError(f"audience must be one of {AUDIENCES}")
    now = now or dt.datetime.now()
    hidden = 0

    bad: list[str] = []

    def safe(name: str) -> tuple[dict, str]:
        f = root / name
        if not f.is_file():
            return {}, ""
        try:
            return read_front_matter(f)
        except FrontMatterError:
            bad.append(name)
            return {}, ""

    proj_fm, proj_body = safe("PROJECT.md")
    roles_fm = safe("ROLES.md")[0]
    principals = {str(p.get("id")): p for p in roles_fm.get("principals") or [] if isinstance(p, dict)}

    decisions, h = _records(root, "decisions", audience, bad); hidden += h
    sessions, h = _records(root, "sessions", audience, bad); hidden += h
    handoffs, h = _records(root, "handoffs", audience, bad); hidden += h
    timeline, h = _records(root, "timeline", audience, bad); hidden += h
    sessions = [s for s in sessions if s["fm"].get("confirmed_by")] + \
               [s for s in sessions if not s["fm"].get("confirmed_by")]
    sessions.sort(key=lambda s: str(s["fm"].get("ended_at") or s["fm"].get("date") or ""), reverse=True)
    decisions.sort(key=lambda d: str(d["fm"].get("id")), reverse=True)

    ledger: list[dict] = []
    if (root / "ledger").is_dir():
        for p in sorted((root / "ledger").glob("*.csv")):
            with p.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    if not _visible(row.get("classification"), audience):
                        hidden += 1
                        continue
                    row["_table"] = p.stem
                    row["_oral_only"] = not (row.get("evidence") or "").strip()
                    ledger.append(row)
    priority = {"disputed": 0, "unverified": 1, "auto-checked": 2, "retracted": 3, "human-verified": 4}
    ledger.sort(key=lambda r: (priority.get(r.get("status") or "unverified", 9), not r["_oral_only"]))
    counts = Counter(r.get("status") or "unverified" for r in ledger)
    oral_only = sum(1 for r in ledger if r["_oral_only"])

    questions = []
    qfm, _ = safe("open-questions.md")
    if qfm:
        questions = [q for q in qfm.get("questions") or [] if isinstance(q, dict)
                     and q.get("status", "open") == "open" and _visible(q.get("classification"), audience)]

    pending = [d for d in decisions if d["fm"].get("status") == "proposed"]
    head = gitutil.head(root) if gitutil.is_repo(root) else None
    return {
        "meta": {
            "generated_at": now.replace(microsecond=0).isoformat(),
            "generated_epoch_ms": int(now.timestamp() * 1000),
            "stale_days": stale_days,
            "commit": head,
            "audience": audience,
            "scope": sorted(VISIBLE[audience]),
            "hidden_items": hidden,
            "unreadable": bad,
            "tool": f"groundwork-lab {__version__}",
            "spec": SPEC_VERSION,
        },
        "project": {"fm": proj_fm, "sections": sections(proj_body)},
        "principals": principals,
        "decisions": decisions,
        "pending_decisions": pending,
        "sessions": sessions,
        "handoffs": handoffs,
        "timeline": timeline,
        "ledger": ledger,
        "verification": {"counts": {s: counts.get(s, 0) for s in STATUS_ORDER},
                         "total": len(ledger), "oral_only": oral_only},
        "questions": questions,
    }


# ------------------------------------------------------------- render
LABELS = {
    "en": {
        "view_for": "View for", "generated": "Generated", "commit": "Commit", "scope": "Visible",
        "hidden": "items withheld from this view",
        "unreadable": "record(s) could not be read and are missing from this page. Run `gw check`:",
        "verified_collapsed": "Show human-verified items", "stale": "This view is {d} days old. The repository may have changed.",
        "goal": "Goal", "state": "Current state", "thinking": "Main line of thinking", "milestones": "Milestones",
        "needs_decision": "Waiting for a decision", "decisions": "Decisions", "verification": "Verification",
        "sessions": "Recent sessions", "questions": "Open questions", "timeline": "Timeline", "handoffs": "Handoffs",
        "n_items": "items", "oral_only": "oral-only (no evidence)", "none": "None.", "decider": "decided by",
        "approved": "approved by", "proposed_by": "proposed by", "unconfirmed": "unconfirmed draft",
        "blocked": "Blocked", "next": "Next", "did": "Did", "routed": "ask",
        "footer": "Generated from the project's files by {tool} (spec v{spec}). This page is read-only; "
                  "the repository is the source of truth.",
        "legend": "Badges",
        "status": {"human-verified": "human-verified", "auto-checked": "auto-checked", "unverified": "unverified",
                   "disputed": "disputed", "retracted": "retracted"},
        "dstatus": {"proposed": "proposed", "accepted": "accepted", "vetoed": "vetoed", "superseded": "superseded"},
    },
    "zh": {
        "view_for": "阅读对象", "generated": "生成时间", "commit": "版本", "scope": "可见范围",
        "hidden": "条内容因保密等级未在此页显示",
        "unreadable": "条记录格式有误，未能显示在本页。请运行 `gw check` 查看：",
        "verified_collapsed": "展开已人工核验的条目", "stale": "本页已生成 {d} 天，仓库内容可能已有变化。",
        "goal": "目标", "state": "当前状态", "thinking": "主线思路", "milestones": "里程碑",
        "needs_decision": "待决定事项", "decisions": "决策记录", "verification": "核验状态",
        "sessions": "最近工作记录", "questions": "待解答问题", "timeline": "阶段时间线", "handoffs": "交接记录",
        "n_items": "条", "oral_only": "仅口述（无证据）", "none": "暂无。", "decider": "决定人",
        "approved": "批准人", "proposed_by": "提议人", "unconfirmed": "未确认草稿",
        "blocked": "卡点", "next": "下一步", "did": "完成", "routed": "请问",
        "footer": "本页由 {tool}（规范 v{spec}）根据项目文件自动生成，只读，以仓库内容为准。",
        "legend": "标识说明",
        "status": {"human-verified": "人工核验", "auto-checked": "自动检查", "unverified": "未核验",
                   "disputed": "有争议", "retracted": "已撤回"},
        "dstatus": {"proposed": "待决定", "accepted": "已通过", "vetoed": "已否决", "superseded": "已被取代"},
    },
}
AUDIENCE_LABEL = {
    "en": {"owner": "Owner / PI", "advisor": "Advisor", "receiver": "Receiver (full record)", "public": "Public"},
    "zh": {"owner": "负责人 / PI", "advisor": "导师", "receiver": "接手人（完整记录）", "public": "公开"},
}


def _template_source(root: Path) -> str:
    custom = root / ".groundwork" / "site" / "template.html.j2"
    if custom.is_file():
        return custom.read_text(encoding="utf-8")
    return resources.files("groundwork").joinpath("site_templates/default.html.j2").read_text(encoding="utf-8")


def validate_rendered(page: str) -> list[str]:
    """Return the mandatory elements (spec §12) missing from a rendered page."""
    missing = [m for m in REQUIRED_MARKERS if f'data-gw="{m}"' not in page]
    return missing


def render(root: Path, data: dict[str, Any], lang: str = "en") -> str:
    env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))
    env.filters["md"] = md
    tpl = env.from_string(_template_source(root))
    page = tpl.render(d=data, L=LABELS[lang], A=AUDIENCE_LABEL[lang][data["meta"]["audience"]],
                      lang=lang, statuses=STATUS_ORDER)
    missing = validate_rendered(page)
    if missing:
        raise TemplateViolation(f"template is missing required element(s): {missing} (spec §12)")
    return page


def build(root: Path, audience: str = "receiver", lang: str = "en", out: Path | None = None,
          now: dt.datetime | None = None) -> Path:
    page = render(root, extract(root, audience, now=now), lang)
    out = out or root / ".groundwork" / "build" / f"{audience}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out
