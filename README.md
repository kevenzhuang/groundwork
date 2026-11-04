# Groundwork

**A lab notebook for AI-era research.** *Move fast in research, with every step on record.*
**放手快科研，步步有据可查。**

> Status: pre-alpha (v0.1.0.dev0, spec v0.2). The file format may still change.

AI makes research artifacts cheap to produce: drafts, code, analyses, literature reviews.
Some things are still scarce:

- What was decided, why, and by whom?
- What has actually been verified, and by whom?
- What does the next person (or agent, or your future self) need in order to continue?

Wet labs answer these questions with the paper lab notebook, and examiners check it at the defense.
Computational and AI-assisted research has no equivalent.

Groundwork is that equivalent. It is a small, open, file-based standard plus a CLI that
keeps a project's record **in plain files in your git repository**:

- **Decisions** with explicit decision rights (T0–T3). Agents may only propose; humans decide.
- **Verification status** for every claim, source, or number:
  `unverified → auto-checked → human-verified`. Only a named human can grant the last step.
- **Sessions and handoffs** captured by answering a few questions, not by writing long documents.
- **Append-only history.** Corrections supersede earlier entries; past records are never rewritten.
- **Confidentiality.** Content is scanned before it is written, so secrets and blocked terms never enter the record.
- **AI-optional.** Every core command works offline with no model at all.

## Quick start

```bash
pip install groundwork-lab        # not yet on PyPI; for now: pip install -e .
cd my-project && git init
gw init . --title "My Study" --owner alice --owner-name "Alice"
gw note "dropped the second baseline: it duplicates the first"
gw check                          # validate against the spec; exit 1 on errors
```

`gw init` creates:

```
PROJECT.md  ROLES.md  DECISION-RIGHTS.md  AGENTS.md  open-questions.md
decisions/  sessions/  handoffs/  timeline/  ledger/  notes/  .groundwork/
```

`AGENTS.md` tells coding agents (Claude Code, Codex, and others) to follow the spec.
Most agents read that file automatically at the start of every session.

## Commands

| Command | Status | What it does |
|---|---|---|
| `gw init` | ✅ | Create the layout from templates; never overwrites existing files |
| `gw note` | ✅ | Append a timestamped note; blocks secrets |
| `gw check` | ✅ | Validate roles, decision rights, decisions, ledger, confidentiality, and integrity |
| `gw end` | planned | Session capture: collect changes, ask only for the reasons, confirm |
| `gw site` | planned | Generate a self-contained, read-only HTML view for each audience |
| `gw ui` | planned | Local UI with Start, End, and Record pages |

The full list of checks is in [spec §7](spec/SPEC.md#7-checks-gw-check).

## Using it in CI

```yaml
# .github/workflows/groundwork.yml
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # full history is needed for the integrity check (E09)
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install groundwork-lab && gw check
```

## Documents

- [Specification](spec/SPEC.md)
- [Design decisions for this repository](docs/decisions/)

## 中文简介

Groundwork 是"AI 时代科研的实验记录本"：一套开放的文件规范，加上一个命令行工具。它把以下内容都以纯文本文件的形式记录在项目的 git 仓库里：

- 科研过程中的决策：谁定的、为什么；
- 核验状态：哪些已经人工核验、哪些只是 AI 声称；
- 交接记录。

它不依赖任何服务器或 AI，离线也能用。AI agent 只能提议，决定和核验都由人来做。

## License

- Code: [Apache-2.0](LICENSE)
- Specification text (`spec/`): [CC-BY-4.0](spec/LICENSE)
