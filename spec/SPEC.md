# Groundwork Specification v0.2

*Research workflows you can trust, hand over, and build on.*
*The open workflow standard for human–AI research.*

- Status: draft, 2026-11-04
- License: CC-BY-4.0 (see `spec/LICENSE`)
- The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are used as described in RFC 2119.
- Items marked **[PENDING]** are waiting on user-research evidence and may change.

Changes since v0.1:
- New sections: capture and storage (§8), confidentiality (§9), identity (§10.2–10.3), publishing views and templates (§12).
- New principles: AI-optional and local-first (§0).
- Verification status, rather than authorship, is now the primary axis (§1.3).

---

## 0. Purpose and principles

Groundwork is a convention for keeping a research project's record in plain files inside a version-controlled repository. Any person or AI agent who opens the repository can then learn the following without asking the previous owner:

- what was done;
- why it was done, and who decided;
- how much of it has been verified;
- what to do next.

Principles:

1. **Files are the source of truth.** No server, database or vendor is required. Tools only read and write these files.
2. **Record turning points and reasons, not everything.** A record that nobody can read is as bad as no record.
3. **Verification first.** The first question is whether something has been checked. Who or what produced it is secondary provenance.
4. **Humans decide; agents propose.** An agent MUST NOT make a decision or grant verification.
5. **Append, don't rewrite.** Corrections are new entries, and history stays visible.
6. **Rules are checked, not trusted.** Any rule that can be checked automatically SHOULD be checked at gates.
7. **Answer, don't write.** Capture SHOULD happen through questions (an interview or a form) followed by human confirmation.
8. **AI-optional.** Every core operation MUST work without an AI model. AI is an optional enhancement.
9. **Local-first.** Tools MUST work offline and MUST NOT send data anywhere unless the user configures it.
10. **Classify before storing.** Confidential content must not enter the record by accident.
11. **Speak the user's language; never translate the record.** Tools SHOULD present prompts, briefings and views in the user's language. They resolve it in this order:
    1. an explicit choice;
    2. the `GW_LANG` environment variable;
    3. the project setting;
    4. the language of the record's own prose (titles and fixed headings are ignored);
    5. the system locale;
    6. English.

    Record content MUST be stored as written, never machine-translated, because translation can distort meaning.

---

## 1. Core concepts

### 1.1 Roles

| Role | Meaning | Count |
|---|---|---|
| `owner` | Ultimately accountable for the project (the "A" in RACI). | Exactly 1 |
| `lead` | Runs day-to-day work. | ≥1 |
| `advisor` | Reviews direction and quality; may veto within their area. | ≥0 |
| `contributor` | Does assigned parts of the work. | ≥0 |
| `receiver` | A person taking over a role. | Per handoff |
| `agent` | Any AI agent. Proposes, and executes within its scope. | ≥0 |

One principal MAY hold several roles. Every agent MUST have a human `sponsor`, who is responsible for the agent's actions.

### 1.2 Decision tiers

| Tier | Rule |
|---|---|
| `T0` | Proposal only. This is the only tier an agent may use. |
| `T1` | Decide and log. |
| `T2` | Decide and notify the listed roles. They may veto within the window (default 3 days). Silence counts as consent. |
| `T3` | Ask first. Approval from the listed role is required before acting. |

Choose a tier by asking three questions:

- Can the decision be reversed?
- How far does its impact reach?
- Does it create a commitment to someone outside the project?

If unsure, use `T2`.

### 1.3 Verification status

Status order:

`unverified` → `auto-checked` → `human-verified`

Side states:

- `disputed`: someone contests the item, with a stated reason.
- `retracted`: the item is withdrawn, with a stated reason. It is kept in the record and never deleted.

Rules:

- Only a human may set `human-verified`.
- A `human-verified` item MUST record `verified_by`, `verified_on` and `method`.
- A tool MAY set `auto-checked` and MUST record which tool and which version did so.
- [PENDING] The labels shown to users may change. The machine values stay fixed.

### 1.4 Evidence, capture and provenance

- `evidence`: a list of pointers (§8.4). An item with no evidence is labeled `oral-only`.
- `capture`:
  - `contemporaneous`: recorded at the time.
  - `reconstructed`: written down later. Less reliable.
- `provenance`: either `human:<id>` or `agent:<id>`, plus a date.

### 1.5 Classification

Every file or item has a `classification`. The default is `internal`.

| Value | Who may see it |
|---|---|
| `public` | Anyone. May be published. |
| `internal` | Project members. |
| `restricted` | Named principals only (§9.3). |
| `secret` | Never stored by Groundwork. The record only names who holds it. |

`ai_allowed` (default `true`) controls whether AI adapters may process the item. When it is `false`, only deterministic tools may read the item.

---

## 2. Repository layout

```
PROJECT.md            # one-page overview
ROLES.md              # principals → roles, scopes, sponsors, key fingerprints
DECISION-RIGHTS.md    # decision catalogue: area → tier → approver role
AGENTS.md             # short rules for agents; points to this spec
timeline/             # one file per stage
decisions/            # NNNN-slug.md
sessions/             # one entry per working session
handoffs/             # handoff reports
ledger/               # tables of verifiable items (*.csv)
notes/                # contemporaneous jots: YYYY-MM-DD.md, written by `gw note`
open-questions.md
.groundwork/
  config.yaml         # project settings (blocklist terms, veto window, collectors)
  spec-version        # version of this spec the project follows
```

The folders `.groundwork/build/` and `.groundwork/index.sqlite` are derived files and SHOULD be gitignored.

---

## 3. File formats

All markdown records begin with YAML front-matter. Fields not listed here are allowed. Every record MAY carry the fields `classification`, `ai_allowed`, `capture` and `provenance`.

### 3.1 `PROJECT.md`

Front-matter fields: `title`, `owner`, `stage`, `updated`.

Body sections, in this order:

1. Goal
2. Current state
3. Main line of thinking
4. Milestones
5. Where things live

Keep it to about one page.

### 3.2 `ROLES.md`

Front-matter field `principals`: a list. Each entry has these fields.

| Field | Required | Format and meaning |
|---|---|---|
| `id` | yes | The stable key every record uses to refer to this principal. It must match `^[a-z][a-z0-9-]{1,31}$`: lowercase ASCII letters, digits and hyphens, 2–32 characters, starting with a letter. It must be unique within the project, compared case-insensitively. An `id` MUST NOT change and MUST NOT be reused (§3.2.1). Examples: `keven`, `arnold-wang`, `claude-1`. |
| `name` | yes | Display name, free-form, in any language and any order (e.g. `庄子钧`, `Zijun "Keven" Zhuang`). Groundwork does not standardize names. |
| `aliases` | no | Other ways people refer to this principal (e.g. `[Keven, 子钧, Zhuang]`). Agents use these to map what humans say to an `id`. |
| `kind` | yes | `human` or `agent` |
| `roles` | yes | A list of roles from §1.1. |
| `scope` | no | Paths or areas the principal may read and write. Default: everything. |
| `since` | no | Date. |
| `until` | no | Date. A principal whose `until` has passed stays in the file, so that old records keep resolving. |
| `sponsor` | agents | The `id` of the responsible human. |
| `git_identity` | no | The email address used in commits. |
| `github` | no | GitHub login, used to verify approvals (§13). It must be a valid GitHub login. |
| `orcid` | no | ORCID iD (`0000-0000-0000-000X`), for authorship and contribution records. |
| `signing_key` | no | A key fingerprint. |

#### 3.2.1 References to principals

Every field that names a principal MUST contain a known `id`, never a display name. These fields are: `owner`, `decider`, `approved_by`, `proposed_by`, `notified`, `confirmed_by`, `verified_by`, `asked_by`, `routed_to`, `principal`, `from`, `to`, `sponsor`, and `confirmed_by_from`.

If a person must be renamed, edit `name` and `aliases`. If an `id` really must change (for example, two people chose the same one), add a new principal with `formerly: <old id>` and set `until` on the old entry. Past records keep the old `id`.

### 3.3 `DECISION-RIGHTS.md`

Front-matter fields:

- `confirmed_by`: the owner's id.
- `confirmed_on`: a date.
- `areas`: a list of entries, each with `area`, `examples`, `tier`, `approver_role` and `veto_window`.

Keep `T3` to about 5–8 areas. The default template is in `templates/project/DECISION-RIGHTS.md`.

### 3.4 `decisions/NNNN-slug.md`

Front-matter fields:

| Field | Requirement |
|---|---|
| `id` | Required |
| `date` | Required |
| `title` | Required |
| `tier` | `T0`, `T1`, `T2` or `T3` |
| `decider` | A human id. Required unless `tier` is `T0`. |
| `proposed_by` | Required if `tier` is `T0` |
| `approved_by` | Required if `tier` is `T3` |
| `notified` | Required if `tier` is `T2` |
| `veto_window` | Required if `tier` is `T2` |
| `status` | `proposed`, `accepted`, `vetoed` or `superseded` |
| `supersedes` | Optional |
| `capture` | Required |

Body sections: Context, Options considered, Decision, Reasons, Consequences, Evidence.

A decision is reversed by writing a new decision that `supersedes` it. A decision MUST NOT be edited after it is `accepted`.

### 3.5 `timeline/NN-stage.md`

Front-matter fields: `stage`, `from`, `to` (empty if the stage is current), `capture`.

Body sections: What we believed, What we tried, What we learned, Why the stage ended, Key decisions.

### 3.6 Ledger tables: `ledger/*.csv`

Required columns:

- `id`
- `status`
- `provenance`
- `verified_by`
- `verified_on`
- `method`
- `evidence`
- `classification`
- `notes`

Tables MAY add domain-specific columns.

### 3.7 `sessions/YYYY-MM-DD-<principal>[-n].md`

Front-matter fields:

- `principal`, `date`, `capture`, `confirmed_by`.
- `base` and `head`: the commit range this session covers. The next capture starts from `head`.
- `ended_at`: an ISO timestamp. Notes written after it belong to the next session.
- `sources`: a list of pointers (§8.4) to what was collected, such as `commit:`, `repo:notes/...` and `archive:` entries.

Body sections:

- Did
- Thinking
- Changes and reasons
- Blocked
- Next
- Unverified items touched

### 3.8 `handoffs/YYYY-MM-DD-<from>-to-<to>.md`

Front-matter fields: `from`, `to`, `role`, `date`, `confirmed_by_from`, `approved_by`.

Body sections:

- Summary
- Current state
- Open work
- Decisions to know
- Unverified and oral-only items
- Traps and unwritten knowledge
- Who to ask about what
- Access to transfer

A handoff MUST NOT contain secrets. It MUST only say who holds them.

### 3.9 `notes/YYYY-MM-DD.md`

An append-only list. Each line has this form:

`- HH:MM [principal] text`

### 3.10 `open-questions.md`

Each entry has: `id`, `question`, `asked_by`, `routed_to`, `date`, `status`, `answer_ref`.

---

## 4. Workflow

The default stages are listed below. A project MAY rename them.

`idea → scope → investigate → synthesize → write → review → release → handoff/archive`

| Gate | Default tier |
|---|---|
| scope → investigate | T2 |
| write → release (submit or publish) | T3 |
| any stage → public release of data, code or a view | T3 |
| handoff | T3 |

At a gate, `gw check` MUST pass, and the approval MUST be recorded as a decision.

---

## 5. Agent protocol

### 5.1 Session start

The agent MUST read, in this order:

1. `AGENTS.md`
2. `PROJECT.md`
3. The latest session entry
4. Any handoffs addressed to its sponsor
5. Open questions routed to its sponsor

It MUST then state its understanding in 3–5 lines before starting work.

### 5.2 During work

An agent MUST:

- stay within the scope given in `ROLES.md`;
- record provenance;
- cite evidence for every claim, or mark the claim `unverified` or `oral-only`;
- write any decision-like change as a `T0` proposal;
- work on a branch and propose changes for review.

An agent MUST NOT:

- set `human-verified`, `verified_by` or `approved_by`;
- act as `decider`;
- edit or delete past decisions, sessions or handoffs;
- write secrets;
- copy `restricted` content into an `internal` record;
- process content where `ai_allowed` is `false`.

### 5.3 Session end (capture)

The agent follows the capture pipeline in §8. When it acts as the interviewer:

- It asks only for what the evidence cannot answer, one question at a time.
- It follows up once if an answer is vague.
- It points out contradictions with the evidence.
- It never fills in an answer on the human's behalf.
- When the human says "confidential" or "don't record", it writes a placeholder (§9.2) instead of the content.

### 5.4 Answering a receiver

The agent:

- uses only content within the receiver's scope and classification;
- cites a file for every answer;
- when it does not know, says so and routes the question to `open-questions.md`.

---

## 6. Human protocol

- The `owner` confirms `ROLES.md` and `DECISION-RIGHTS.md`:
  - at project start;
  - whenever roles change.
- A confirmation means "I checked this for distortion". It is not a polish pass.
- Notices of `T2` decisions MUST be visible to the people listed as `notified`, for example as a PR, a mention or a message.
- Vetoes and dissent are recorded. They are not erased.

---

## 7. Checks (`gw check`)

Checks that report an **error** block a gate. Checks that report a **warning** do not.

Errors:

- E01: A required file is missing (`PROJECT.md`, `ROLES.md`, `DECISION-RIGHTS.md`, `AGENTS.md`).
- E02: The front-matter of `ROLES.md` is invalid, there is not exactly one `owner`, or an agent has no human `sponsor`.
- E03: A decision has an invalid `tier` or `status`, or is missing a field that its tier requires (§3.4).
- E04: A decision's `decider`, or the `approved_by` of a `T3` decision, is an agent.
- E05: A ledger row has status `human-verified` but is missing `verified_by`, `verified_on` or `method`.
- E06: A ledger row's `verified_by` is an agent, or is not a known principal.
- E07: A secret pattern was found in a tracked file (§9.1).
- E08: A file contains a term from the project blocklist (§9.1).
- E09: Integrity: an accepted decision, a confirmed session or a confirmed handoff was modified (requires git history).
- E10: An invalid enum value appears (`classification`, `status`, `capture`).
- E12: A field that names a principal (§3.2.1) refers to an `id` that is not in `ROLES.md`, or a principal entry has a malformed `id`, `github` or `orcid`.

Warnings:

- W01: `DECISION-RIGHTS.md` has not been confirmed by the owner.
- W02: There are open questions older than 30 days.
- W03: Items marked `unverified` or `oral-only` are referenced by a release artifact.
- W04: A session draft has not been confirmed.

Domain plugins MAY add checks. A plugin MUST NOT set `human-verified`.

---

## 8. Capture and storage

### 8.1 Triggers

Capture is triggered by **change**, not by AI sessions. Ways to start it:

- `gw end`, run by the user;
- an agent session-end hook;
- a reminder on commit or at a scheduled time.

### 8.2 Pipeline

1. **Collect.** Gather everything since the last confirmed session. If there is no confirmed session yet, start from the commit that adopted Groundwork, so that scaffolding and older history are not asked about. Collect:
   - git changes;
   - document snapshots;
   - agent session logs;
   - entries in `notes/`.
2. **Classify.** Run the scanners in §9.1. If anything is found, stop and ask the user what to do.
3. **Draft.** Fill in the "Changes" section automatically, and leave the reasons blank.
4. **Ask.** Ask only for the blanks. This can be done by CLI prompts, a form, an agent dialogue or voice.
5. **Confirm.** The human approves. The record is committed on a branch and a PR is opened.
6. **Archive.** Raw sources are archived (§8.3), and views are regenerated.

Every step MUST work without AI. AI adapters MAY summarize, ask follow-up questions or transcribe audio, but only for items where `ai_allowed` is `true`.

### 8.3 Archive

- Archiving is **off by default**. When it is enabled, raw agent logs and any other large or sensitive raw material are stored in `.groundwork/archive/`, which is gitignored. Nothing is written outside the project folder. The record holds a pointer and a sha256 hash.
- Backups of the archive SHOULD be encrypted.
- Tools MUST NOT depend on the retention settings of agent tools. For example, some tools delete their transcripts after 30 days by default, so logs are copied into the archive at capture time.

### 8.4 Pointers

| Form | Meaning |
|---|---|
| `repo:<path>[#Lstart-Lend]` | A file in the repository |
| `commit:<sha>` | A git commit |
| `archive:<relative-path>@sha256:<hex>` | A file in the local archive |
| `url:<https-url>` | An external resource; add a revision id where one exists |
| `doc:<provider>:<id>@<revision>` | A document revision held by a provider |

---

## 9. Confidentiality

### 9.1 Scanning before writing

Before anything is written or committed, tools MUST scan for:

- known secret formats (API keys, private keys, tokens, passwords in assignments);
- private-network IP addresses;
- email addresses and phone numbers that are not on the project allowlist;
- terms from the project blocklist in `.groundwork/config.yaml`.

When a scan finds something, the tool MUST stop and offer three choices: redact it, mark it `restricted`, or skip it.

### 9.2 Placeholders

Content left out for confidentiality is replaced with:

`[withheld: <category>; ask <principal-id>]`

### 9.3 Restricted storage

`restricted` content MUST NOT be stored in plain text in a repository that anyone outside its named principals can read. Store it in one of these ways:

- in a separate repository with limited access;
- encrypted inside the repository (for example with age or sops).

The main record holds a placeholder.

### 9.4 Leaks

Removing leaked content is the only sanctioned rewrite of history. The procedure is:

1. Purge the content from history.
2. Rotate any exposed credentials.
3. Write a `T3` incident decision that records the category of the leak, but not its content.

---

## 10. Integrity and identity

### 10.1 History

- The main line MUST be protected: no force-push and no history rewrite, except under §9.4.
- A copy SHOULD exist where the author cannot rewrite it, such as a hosted remote or a mirror.

### 10.2 Identity

- Each principal MUST commit under their own git identity, as listed in `ROLES.md`. Agents MUST NOT use a human's identity.
- Commits made by agents SHOULD carry these trailers:
  - `Agent: <id>`
  - `Model: <model>`
  - `Session: <ref>`
  - `Sponsor: <human-id>`

### 10.3 Signing

- Commits SHOULD be signed.
- When signing keys are registered, a change that sets `human-verified` or `approved_by` MUST meet one of these conditions:
  - it was committed with the named human's key; or
  - it was merged by a PR that the named human approved.
- The aim is tamper-evidence, not tamper-proofing. Sharing keys defeats this rule.

---

## 11. Adopting Groundwork in an existing project (backfill)

1. Run `gw init` to create the layout.
2. The owner confirms roles and decision rights.
3. An agent drafts the timeline and candidate decisions from the existing artifacts. Every item is marked `capture: reconstructed` and links to evidence. Git commit dates MUST NOT be forged.
4. An agent lists the choices an agent made in the past that a human never explicitly approved. Humans accept or reject each one.
5. The lead fills in the reasons and confirms.
6. From then on, use capture (§8).

---

## 12. Views (`gw site`)

- Views are built in two steps:
  1. Extract per-audience data (`owner`, `advisor`, `receiver`, `public`), applying scope and classification.
  2. Render the data with a template.
- Every template MUST render these elements:
  - a header with the generation time, source commit, audience, scope and a staleness notice;
  - verification badges with fixed semantics: `unverified` and `oral-only` must be visibly marked;
  - each decision's tier and approval state;
  - a footer stating that the view is generated and that the repository is authoritative.
- Projects MAY override the theme, section order and language, and MAY add plugin sections. They MUST NOT drop the required elements.
- The default output is a single self-contained HTML file.
- Publishing a view online requires access control. Publishing publicly is a `T3` decision.

---

## 13. GitHub-native mode (default)

The record lives in a GitHub repository. GitHub supplies viewing, notifications, identity and approvals. Groundwork supplies the spec, the checks and the automation.

1. **Status page.** On every push to the main line, automation regenerates `STATUS.md` (advisor-level view, §12 rules apply) and commits it. A tool MUST NOT hand-edit it.
2. **Gate.** `gw check` runs on every pull request. The main line SHOULD be protected so that a failing check blocks the merge.
3. **Approvals.** A T2 or T3 decision becomes `accepted` by merging a pull request that adds or changes it.
   - Every principal named in `approved_by` MUST have approved that pull request on GitHub, under the `github` login listed in `ROLES.md`.
   - `gw approvals` verifies this from the pull request's reviews.
   - An approval written in a file without a matching GitHub review is invalid.
4. **Notifications.** T2 notices and T3 requests are made by requesting a review from the relevant people on the pull request.
5. **Start and end.** Users interact through two actions: *start* (`gw start`, a briefing) and *end* (`gw end`, the capture). Most users trigger them by telling their agent.

## 14. Out of scope (v0.2)

- A hosted platform, user accounts or real-time collaboration
- Wet-lab ELN features
- Capture from chat tools

## 15. Pending items [PENDING]

- Which first experience to promote: personal resume or team handoff.
- The default weight of decision rights.
- The priority of a citation plugin.
- The user-facing labels for verification status.
- The default veto window and the gate list.
