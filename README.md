# Groundwork

**Research workflows you can trust, hand over, and build on.**
**可信、可交接、可传承的科研工作流。**

*The open workflow standard and platform for human–AI research.*

> Status: pre-alpha (v0.1.0.dev0, spec v0.2). The file format may still change.

## Why

**Vision:** make research in the age of AI trustworthy, continuous, and accountable.

AI makes research artifacts cheap to produce: drafts, code, analyses, literature reviews.
It does not make them trustworthy. Some questions are as hard to answer as ever:

- **Trust.** What has actually been verified, and by whom?
- **Hand over.** What does the next person (or agent, or your future self) need in order to continue?
- **Build on.** What was decided, why, by whom, and with what authority?

Wet labs answer these questions with the paper lab notebook, which examiners check at the defense.
Computational and AI-assisted research has no equivalent standard.

Groundwork is that standard, plus the platform built on it. The first layer is an open,
file-based specification and a CLI that keep a project's record **in plain files in your git repository**:

- **Decisions** with explicit decision rights (T0–T3). Agents may only propose; humans decide.
- **Verification status** for every claim, source, or number:
  `unverified → auto-checked → human-verified`. Only a named human can grant the last step.
- **Sessions and handoffs** captured by answering a few questions, not by writing long documents.
- **Append-only history.** Corrections supersede earlier entries; past records are never rewritten.
- **Confidentiality.** Content is scanned before it is written, so secrets and blocked terms never enter the record.
- **AI-optional.** Every core command works offline with no model at all.
- **Your language.** Prompts, briefings and pages follow the language you write in (currently English and Chinese,
  and new languages are easy to add). What you write is stored as written, never translated.

The layers above it, in progress, are: session capture (`gw end`), per-audience views
(`gw site`), a local UI, agent integrations, and later a lab hub for multi-project oversight
and approvals. Every layer reads and writes the same open files, so there is no lock-in.

## Quick start: one sentence

Open your project in your AI agent (Claude Code, Codex, …) and say:

> Set up Groundwork for this project, following
> https://github.com/kevenzhuang/groundwork/blob/main/docs/agent-setup.md

From then on, you only need two words:

- **"start"** (开工): where things stand, what's blocked, what's next, and what is waiting for you.
- **"end"** (收工): the agent asks you a few questions and records the answers. You confirm by merging its pull request.

Your advisor and PI see the latest state on the repository's `STATUS.md`, on the web or in the
GitHub mobile app. They approve decisions by approving the pull request.

### Without an agent

```bash
pipx install git+https://github.com/kevenzhuang/groundwork
gw init . --title "My Study" --owner alice --github alice-gh
gw start        # briefing
gw note "dropped the second baseline: it duplicates the first"
gw end          # capture: asks only for reasons
gw check        # validate against the spec
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
| `gw init` | ✅ | Create the layout and the GitHub workflow; never overwrites existing files |
| `gw start` | ✅ | Start-of-work briefing: last session, blocked, next, decisions and questions waiting for you |
| `gw status` | ✅ | Regenerate `STATUS.md` (run automatically on every push to `main`) |
| `gw approvals` | ✅ | Verify that `approved_by` matches real GitHub PR approvals (run automatically on PRs) |
| `gw note` | ✅ | Append a timestamped note; blocks secrets |
| `gw check` | ✅ | Validate roles, decision rights, decisions, ledger, confidentiality, and integrity |
| `gw end` | ✅ | Session capture: collect git changes, notes, and agent transcripts; ask only for the reasons; confirm. `--answers` lets agents run it non-interactively; agents cannot `--confirm` |
| `gw site` | ✅ | Self-contained read-only HTML per audience (`--for owner|advisor|receiver|public`, `--lang en|zh`, `--all`). Restricted items never rendered; mandatory badges/header/footer enforced even for custom templates |
| `gw ui` | planned | Local UI with Start, End, and Record pages |

| `gw upgrade` | ✅ | Move a project to the installed tool's spec version (reviewed as a PR) |
| `gw who` | ✅ | Find a member's id from a name or alias (`gw who 王老师`) |

## Updates never surprise you

- Each project declares the spec version it follows, and its GitHub workflow installs that exact tagged release.
  A new Groundwork release never changes the rules for a project that hasn't upgraded.
- Rules introduced in a newer spec appear only as **warnings** until you run `gw upgrade`.
- `gw start` tells you when an upgrade is available. No network access is needed: it compares local versions.
- `gw upgrade` updates the project's spec copy, the workflow pin and any missing settings, shows what changed
  ([CHANGELOG](CHANGELOG.md)), and re-runs the checks. You review and merge it like any other change.

To update the tool itself: `pipx upgrade groundwork-lab`, or reinstall from GitHub.

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

**可信、可交接、可传承的科研工作流。**

愿景：让 AI 时代的科研可信、可传承、权责分明。

Groundwork 是人与 AI 协同科研的开放工作流标准与平台。它的底层是一套开放的文件规范，把以下内容都以纯文本文件的形式记录在项目的 git 仓库里：

- **可信**：每条结论、文献和数字的核验状态。哪些已经人工核验，哪些只是 AI 声称，"人工核验"只能由具名的人授予。
- **可交接**：访谈式的收工记录和交接报告。接手的人不用你复述，就能看懂项目。
- **可传承**：决策记录和决策权。谁定的、为什么、有没有越权，并且历史只能追加、不能改写。

在这套规范之上，逐步建设采集工具、按读者生成的视图、本地界面、agent 集成，以及实验室级的管理平台。所有层读写的都是同一套开放文件，不会把用户锁死在某个工具里。核心功能离线、不依赖 AI 也能运行。AI agent 只能提议，决定和核验由人来做。

## License

- Code: [Apache-2.0](LICENSE)
- Specification text (`spec/`): [CC-BY-4.0](spec/LICENSE)
