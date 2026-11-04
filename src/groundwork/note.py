"""`gw note`: append a contemporaneous jot (spec §3.9). Scans before writing (§9.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .project import load_config
from .scan import Finding, scan_text


class BlockedNote(RuntimeError):
    def __init__(self, findings: list[Finding]):
        self.findings = findings
        kinds = ", ".join(sorted({f.kind for f in findings}))
        super().__init__(f"note not written: possible confidential content ({kinds})")


def add_note(root: Path, principal: str, text: str, now: dt.datetime | None = None,
             allow_flagged: bool = False) -> Path:
    text = " ".join(text.split())
    if not text:
        raise ValueError("empty note")
    cfg = load_config(root)
    findings = scan_text(text, Path("notes"), cfg.get("blocklist"), cfg.get("email_allowlist"))
    hard = [f for f in findings if f.kind.startswith("secret:") or f.kind == "blocklist"]
    if hard or (findings and not allow_flagged):
        raise BlockedNote(hard or findings)
    now = now or dt.datetime.now()
    path = root / "notes" / f"{now.date().isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# Notes {now.date().isoformat()}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"- {now.strftime('%H:%M')} [{principal}] {text}\n")
    return path
