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
