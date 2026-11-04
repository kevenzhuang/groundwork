"""Confidentiality scanners (spec §9.1). Deterministic; no network, no AI."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

# (name, pattern). Kept conservative to limit false positives.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[abpsr]-[A-Za-z0-9-]{10,}\b")),
    ("password-assignment", re.compile(
        r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[^\s'\"]{6,}")),
]

PRIVATE_IP = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

TEXT_SUFFIXES = {".md", ".txt", ".csv", ".yaml", ".yml", ".json", ".tex", ".bib", ".py", ".toml", ".html"}


@dataclass
class Finding:
    path: Path
    line: int
    kind: str  # secret:<name> | private-ip | email | blocklist
    excerpt: str


def _excluded(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def iter_text_files(root: Path, exclude: list[str]):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith(".git/") or _excluded(rel, exclude):
            continue
        if p.suffix.lower() in TEXT_SUFFIXES or p.name in {"AGENTS.md", "CLAUDE.md"}:
            yield p


def _mask(s: str) -> str:
    s = s.strip()
    return s if len(s) <= 12 else s[:6] + "…" + s[-3:]


def scan_text(
    text: str,
    path: Path,
    blocklist: list[str] | None = None,
    email_allowlist: list[str] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    blocklist = [b for b in (blocklist or []) if b]
    allow = {e.lower() for e in (email_allowlist or [])}
    for n, line in enumerate(text.splitlines(), 1):
        for name, pat in SECRET_PATTERNS:
            for m in pat.finditer(line):
                findings.append(Finding(path, n, f"secret:{name}", _mask(m.group(0))))
        for m in PRIVATE_IP.finditer(line):
            findings.append(Finding(path, n, "private-ip", m.group(0)))
        for m in EMAIL.finditer(line):
            addr = m.group(0).lower()
            if addr in allow or addr.endswith("@users.noreply.github.com") or addr.endswith(".example"):
                continue
            findings.append(Finding(path, n, "email", m.group(0)))
        low = line.lower()
        for term in blocklist:
            if term.lower() in low:
                findings.append(Finding(path, n, "blocklist", term))
    return findings


def scan_tree(root: Path, config: dict) -> list[Finding]:
    exclude = list(config.get("scan_exclude") or [])
    out: list[Finding] = []
    for p in iter_text_files(root, exclude):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        out.extend(scan_text(text, p, config.get("blocklist"), config.get("email_allowlist")))
    return out
