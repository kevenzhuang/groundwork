"""Command-line interface: `gw`. User-facing text adapts to the user's language (see i18n.py)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from . import SPEC_VERSION, __version__, gitutil, i18n
from .check import run_check
from .init import init_project
from .model import parse_roster, read_front_matter
from .note import BlockedNote, add_note
from .project import NotAProject, find_root

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Groundwork: research workflows you can trust, hand over, and build on. Spec v" + SPEC_VERSION,
)
_STATE: dict[str, Optional[str]] = {"lang": None}


@app.callback()
def _main(lang: Optional[str] = typer.Option(None, "--lang", help="Interface language: en | zh (default: auto).")):
    _STATE["lang"] = lang


def _lang(root: Path | None = None) -> str:
    return i18n.resolve(root, _STATE["lang"])


def _t(root: Path | None, key: str, **kw) -> str:
    return i18n.t(key, _lang(root), **kw)


def _root() -> Path:
    try:
        return find_root()
    except NotAProject as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(2)


def _default_principal(root: Path) -> str:
    env = os.environ.get("GW_PRINCIPAL")
    if env:
        return env
    try:
        fm, _ = read_front_matter(root / "ROLES.md")
        roster, _ = parse_roster(fm)
    except (OSError, ValueError):
        return "unknown"
    email = gitutil.user_email(root)
    for p in roster.principals.values():
        if email and p.git_identity == email:
            return p.id
    owners = roster.owners()
    return owners[0].id if owners else "unknown"


@app.command()
def version() -> None:
    """Show tool and spec versions."""
    typer.echo(f"groundwork-lab {__version__} (spec v{SPEC_VERSION})")


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project directory."),
    title: str = typer.Option(..., "--title", "-t", prompt=True, help="Project title."),
    owner: str = typer.Option(..., "--owner", prompt="Owner id (short, e.g. keven)", help="Owner principal id."),
    owner_name: str = typer.Option("", "--owner-name", help="Owner display name."),
    owner_git: Optional[str] = typer.Option(None, "--owner-git", help="Owner git email (default: git config)."),
    github: Optional[str] = typer.Option(None, "--github", help="Owner's GitHub login (used to verify approvals)."),
    no_workflow: bool = typer.Option(False, "--no-workflow", help="Don't add the GitHub Actions workflow."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
) -> None:
    """Create the Groundwork layout in PATH (never overwrites without --force)."""
    lang = i18n.normalize(_STATE["lang"]) or i18n.detect_text(title, min_letters=2) or i18n.resolve(None)
    written = init_project(path, title, owner, owner_name or owner, owner_git, force,
                           owner_github=github, github_workflow=not no_workflow,
                           language=lang if i18n.normalize(_STATE["lang"]) else "auto")
    for w in written:
        typer.echo(i18n.t("init.created", lang, path=w.relative_to(path.resolve()) if w.is_absolute() else w))
    typer.secho(i18n.t("init.done", lang, path=path.resolve()), fg="green")
    typer.echo(i18n.t("init.next", lang))


@app.command()
def note(
    text: list[str] = typer.Argument(..., help="The note text."),
    principal: Optional[str] = typer.Option(None, "--as", help="Principal id (default: from git email)."),
    allow_flagged: bool = typer.Option(False, "--allow-flagged",
                                       help="Write even if emails/IPs are detected (never secrets)."),
) -> None:
    """Append a timestamped note to notes/YYYY-MM-DD.md."""
    root = _root()
    who = principal or _default_principal(root)
    try:
        path = add_note(root, who, " ".join(text), allow_flagged=allow_flagged)
    except BlockedNote as exc:
        typer.secho(str(exc), fg="red", err=True)
        for f in exc.findings:
            typer.echo(f"  {f.kind}: {f.excerpt}", err=True)
        typer.echo(_t(root, "note.blocked_hint"), err=True)
        raise typer.Exit(1)
    typer.echo(_t(root, "note.ok", path=path.relative_to(root)))


@app.command()
def end(
    principal: Optional[str] = typer.Option(None, "--as", help="Principal id (default: from git email)."),
    answers_file: Optional[Path] = typer.Option(
        None, "--answers", help="YAML with did/thinking/blocked/next/unverified/reasons (for agents and scripts)."),
    draft: bool = typer.Option(False, "--draft", help="Don't ask questions; write a draft with blanks."),
    preview: bool = typer.Option(False, "--preview", help="Only show what changed; write nothing."),
    confirm: bool = typer.Option(False, "--confirm", help="Mark the session confirmed by --as (humans only)."),
    archive_logs: Optional[bool] = typer.Option(None, "--archive-logs/--no-archive-logs",
                                                help="Archive agent transcripts into .groundwork/archive (default: config)."),
    lang: Optional[str] = typer.Option(None, "--lang", help="en | zh (default: auto)."),
) -> None:
    """End a working session: collect changes, ask only for reasons, write sessions/…md."""
    import yaml

    from .capture import SECTIONS, Blocked, collect, group_changes, missing_reasons, write_session

    _STATE["lang"] = lang or _STATE["lang"]
    root = _root()
    lang = _lang(root)
    T = lambda k, **kw: i18n.t(k, lang, **kw)  # noqa: E731
    who = principal or _default_principal(root)
    roster, _ = parse_roster(read_front_matter(root / "ROLES.md")[0])
    is_agent = roster.is_agent(who)
    if confirm and is_agent:
        typer.secho(T("end.agent_confirm"), fg="red", err=True)
        raise typer.Exit(1)

    col = collect(root, include_agent_logs=archive_logs)
    answers: dict = {}
    if answers_file:
        answers = yaml.safe_load(answers_file.read_text(encoding="utf-8")) or {}

    span = T("end.since", t=f"{col.since:%Y-%m-%d %H:%M}") if col.since else T("end.first")
    typer.secho(T("end.header", who=who) + span, bold=True)
    typer.echo(T("end.summary", c=len(col.changes), n=len(col.notes), a=len(col.agent_logs)))

    if preview:
        for c in col.changes:
            typer.echo(f"  {c.status:>2} {c.path}" + ("" if c.committed else "  (uncommitted)"))
        for n in col.notes:
            typer.echo(f"  note {n.when:%Y-%m-%d %H:%M} [{n.principal}] {n.text}")
        return

    interactive = not (draft or answers_file)
    if interactive:
        reasons = dict(answers.get("reasons") or {})
        for label, members in group_changes([c for c in col.changes if not reasons.get(c.path)]).items():
            q = T("end.why_one", x=label) if len(members) == 1 else T("end.why_many", n=len(members), x=label)
            r = typer.prompt(q, default="", show_default=False)
            if r.strip():
                for c in members:
                    reasons[c.path] = r.strip()
        answers["reasons"] = reasons
        for key in SECTIONS:
            if not answers.get(key):
                answers[key] = typer.prompt(T(f"end.q.{key}"), default="", show_default=False)
        if not is_agent and not confirm:
            confirm = typer.confirm(T("end.confirm"), default=True)

    try:
        path = write_session(root, who, col, answers, confirm=confirm and not is_agent, archive=True)
    except Blocked as exc:
        typer.secho(str(exc), fg="red", err=True)
        for f in exc.findings:
            typer.echo(f"  {f.kind}: {f.excerpt}", err=True)
        typer.echo(T("end.blocked_hint"), err=True)
        raise typer.Exit(1)

    missing = missing_reasons(col, answers)
    typer.secho(T("end.wrote", path=path.relative_to(root)), fg="green")
    if missing:
        files = ", ".join(missing[:5]) + (" …" if len(missing) > 5 else "")
        typer.secho(T("end.missing", n=len(missing), files=files), fg="yellow")
    if not confirm or is_agent:
        typer.echo(T("end.unconfirmed"))
    typer.echo(T("end.next"))


@app.command()
def start(principal: Optional[str] = typer.Option(None, "--as", help="Principal id (default: from git email)."),
          lang: Optional[str] = typer.Option(None, "--lang", help="en | zh (default: auto).")) -> None:
    """Start-of-work briefing: where things stand, what's next, what needs you."""
    from .status import briefing

    _STATE["lang"] = lang or _STATE["lang"]
    root = _root()
    typer.echo(briefing(root, principal or _default_principal(root), lang=_lang(root)))


@app.command()
def status(
    stdout: bool = typer.Option(False, "--stdout", help="Print instead of writing STATUS.md."),
    lang: Optional[str] = typer.Option(None, "--lang", help="en | zh (default: auto)."),
) -> None:
    """Regenerate STATUS.md, the status page GitHub shows (spec §13)."""
    from .status import render_status, write_status

    _STATE["lang"] = lang or _STATE["lang"]
    root = _root()
    lang = _lang(root)
    if stdout:
        typer.echo(render_status(root, lang))
    else:
        typer.secho(i18n.t("status.wrote", lang, path=write_status(root, lang).relative_to(root)), fg="green")


@app.command()
def approvals(
    reviews: Path = typer.Option(..., "--reviews", help="JSON from GET /repos/{o}/{r}/pulls/{n}/reviews"),
    changed: Path = typer.Option(..., "--changed", help="File listing paths changed by the PR, one per line."),
    author: Optional[str] = typer.Option(None, "--author", help="PR author's GitHub login."),
) -> None:
    """Verify that approved_by in changed decisions matches real GitHub PR approvals (spec §13.3)."""
    from .approvals import verify

    root = _root()
    files = [l.strip() for l in changed.read_text(encoding="utf-8").splitlines() if l.strip()]
    issues = verify(root, files, json.loads(reviews.read_text(encoding="utf-8")), author)
    for i in issues:
        typer.secho(f"E11 error   {i.path}: {i.message}", fg="red")
    typer.secho(("✗ " if issues else "✓ ") + f"{len(issues)} approval problem(s)", fg="red" if issues else "green")
    if issues:
        raise typer.Exit(1)


@app.command()
def site(
    audience: str = typer.Option("receiver", "--for", help="owner | advisor | receiver | public"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output file (default .groundwork/build/<audience>.html)."),
    all_: bool = typer.Option(False, "--all", help="Build owner, advisor and receiver views."),
    lang: Optional[str] = typer.Option(None, "--lang", help="en | zh (default: auto)."),
) -> None:
    """Generate a self-contained, read-only HTML view of the record."""
    from .site import AUDIENCES, TemplateViolation, build

    _STATE["lang"] = lang or _STATE["lang"]
    root = _root()
    lang = _lang(root)
    targets = ["owner", "advisor", "receiver"] if all_ else [audience]
    for a in targets:
        if a not in AUDIENCES:
            typer.secho(f"unknown audience: {a}", fg="red", err=True)
            raise typer.Exit(2)
        try:
            path = build(root, a, lang, out if not all_ else None)
        except TemplateViolation as exc:
            typer.secho(str(exc), fg="red", err=True)
            raise typer.Exit(1)
        shown = path.relative_to(root) if path.is_relative_to(root) else path
        typer.secho(i18n.t("site.wrote", lang, path=shown, aud=a, lng=lang), fg="green")
    if "public" in targets:
        typer.secho(i18n.t("site.public", lang), fg="yellow")


@app.command()
def check(
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors."),
) -> None:
    """Validate the project against the spec. Exit 1 on errors."""
    root = _root()
    issues = run_check(root)
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    if as_json:
        typer.echo(json.dumps([i.as_dict() for i in issues], ensure_ascii=False, indent=2))
    else:
        for i in issues:
            color = "red" if i.level == "error" else "yellow"
            typer.secho(f"{i.code} {i.level:7} {i.path}: {i.message}", fg=color)
        summary = _t(root, "check.summary", e=len(errors), w=len(warnings))
        typer.secho(("✗ " if errors else "✓ ") + summary, fg="red" if errors else "green")
    if errors or (strict and warnings):
        raise typer.Exit(1)


if __name__ == "__main__":  # pragma: no cover
    app()
