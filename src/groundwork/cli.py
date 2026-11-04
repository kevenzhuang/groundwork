"""Command-line interface: `gw`."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from . import SPEC_VERSION, __version__, gitutil
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
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
) -> None:
    """Create the Groundwork layout in PATH (never overwrites without --force)."""
    written = init_project(path, title, owner, owner_name or owner, owner_git, force)
    for w in written:
        typer.echo(f"  created {w.relative_to(path.resolve()) if w.is_absolute() else w}")
    typer.secho(f"Initialized Groundwork project in {path.resolve()}", fg="green")
    typer.echo("Next: edit PROJECT.md, review ROLES.md and DECISION-RIGHTS.md, then run `gw check`.")


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
        typer.echo("Rephrase without it, or write a placeholder like [withheld: credential; ask <id>].", err=True)
        raise typer.Exit(1)
    typer.echo(f"noted → {path.relative_to(root)}")


@app.command()
def end(
    principal: Optional[str] = typer.Option(None, "--as", help="Principal id (default: from git email)."),
    answers_file: Optional[Path] = typer.Option(
        None, "--answers", help="YAML with did/thinking/blocked/next/unverified/reasons (for agents and scripts)."),
    draft: bool = typer.Option(False, "--draft", help="Don't ask questions; write a draft with blanks."),
    confirm: bool = typer.Option(False, "--confirm", help="Mark the session confirmed by --as (humans only)."),
    no_agent_logs: bool = typer.Option(False, "--no-agent-logs", help="Don't archive agent transcripts."),
) -> None:
    """End a working session: collect changes, ask only for reasons, write sessions/…md."""
    import yaml

    from .capture import SECTIONS, Blocked, collect, group_changes, missing_reasons, write_session
    from .model import parse_roster

    root = _root()
    who = principal or _default_principal(root)
    roster, _ = parse_roster(read_front_matter(root / "ROLES.md")[0])
    is_agent = roster.is_agent(who)
    if confirm and is_agent:
        typer.secho("An agent cannot confirm a session (spec §5.2). Ask the human to confirm.", fg="red", err=True)
        raise typer.Exit(1)

    col = collect(root, include_agent_logs=not no_agent_logs)
    answers: dict = {}
    if answers_file:
        answers = yaml.safe_load(answers_file.read_text(encoding="utf-8")) or {}

    typer.secho(f"Session for {who}" + (f" since {col.since:%Y-%m-%d %H:%M}" if col.since else " (first session)"),
                bold=True)
    typer.echo(f"  {len(col.changes)} changed file(s), {len(col.notes)} note(s), "
               f"{len(col.agent_logs)} agent transcript(s) to archive")

    interactive = not (draft or answers_file)
    if interactive:
        reasons = dict(answers.get("reasons") or {})
        for label, members in group_changes([c for c in col.changes if not reasons.get(c.path)]).items():
            what = f"`{label}`" if len(members) == 1 else f"{len(members)} files in `{label}`"
            r = typer.prompt(f"  Why did {what} change? (Enter to skip)", default="", show_default=False)
            if r.strip():
                for c in members:
                    reasons[c.path] = r.strip()
        answers["reasons"] = reasons
        prompts = {
            "did": "What did you do? (one line is fine)",
            "thinking": "What were you thinking or trying?",
            "blocked": "Anything blocked?",
            "next": "What's next?",
            "unverified": "Anything you relied on that isn't verified yet?",
        }
        for key in SECTIONS:
            if not answers.get(key):
                answers[key] = typer.prompt(f"  {prompts[key]}", default="", show_default=False)
        if not is_agent and not confirm:
            confirm = typer.confirm("Confirm this record as accurate?", default=True)

    try:
        path = write_session(root, who, col, answers, confirm=confirm and not is_agent,
                             archive=not no_agent_logs)
    except Blocked as exc:
        typer.secho(str(exc), fg="red", err=True)
        for f in exc.findings:
            typer.echo(f"  {f.kind}: {f.excerpt}", err=True)
        typer.echo("Remove it or use a placeholder like [withheld: credential; ask <id>].", err=True)
        raise typer.Exit(1)

    missing = missing_reasons(col, answers)
    typer.secho(f"wrote {path.relative_to(root)}", fg="green")
    if missing:
        typer.secho(f"  {len(missing)} change(s) without a reason: " + ", ".join(missing[:5])
                    + (" …" if len(missing) > 5 else ""), fg="yellow")
    if not confirm or is_agent:
        typer.echo("  Draft is unconfirmed. A human confirms with: gw end --confirm  (or edit and set confirmed_by)")
    typer.echo("  Next: review, commit, and open a PR.")


@app.command()
def site(
    audience: str = typer.Option("receiver", "--for", help="owner | advisor | receiver | public"),
    lang: str = typer.Option("en", "--lang", help="en | zh"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output file (default .groundwork/build/<audience>.html)."),
    all_: bool = typer.Option(False, "--all", help="Build owner, advisor and receiver views."),
) -> None:
    """Generate a self-contained, read-only HTML view of the record."""
    from .site import AUDIENCES, TemplateViolation, build

    root = _root()
    targets = ["owner", "advisor", "receiver"] if all_ else [audience]
    for a in targets:
        if a not in AUDIENCES or lang not in ("en", "zh"):
            typer.secho(f"unknown audience/lang: {a}/{lang}", fg="red", err=True)
            raise typer.Exit(2)
        try:
            path = build(root, a, lang, out if not all_ else None)
        except TemplateViolation as exc:
            typer.secho(str(exc), fg="red", err=True)
            raise typer.Exit(1)
        shown = path.relative_to(root) if path.is_relative_to(root) else path
        typer.secho(f"wrote {shown}  ({a}, {lang})", fg="green")
    if "public" in targets:
        typer.secho("Publishing a public view is a T3 decision (spec §12).", fg="yellow")


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
        summary = f"{len(errors)} error(s), {len(warnings)} warning(s)"
        typer.secho(("✗ " if errors else "✓ ") + summary, fg="red" if errors else "green")
    if errors or (strict and warnings):
        raise typer.Exit(1)


if __name__ == "__main__":  # pragma: no cover
    app()
