---
id: "0003"
date: 2026-11-04
title: GitHub is the default platform; Groundwork is the standard and the automation
tier: T3
decider: keven
approved_by: keven
status: accepted
capture: contemporaneous
---

## Context

Usability review: the local-first design required users to manage local files, archive
folders, and to share HTML files by messaging apps. The owner judged this too complex and
not standardized enough. Sharing a record by chat message defeats the purpose of a record.

## Options considered

- Build our own hosted console now. Large effort, hosting, accounts, and security.
- Local files plus HTML sent by message. Simple to build, but unstandardized and stale.
- **Use GitHub as the platform.** Groundwork supplies the spec, checks, and automation.

## Decision

GitHub-native mode is the default:

- The record lives in a private GitHub repository. Members are invited collaborators.
  Labs may use an organization account.
- `STATUS.md` is regenerated on every push to main. GitHub renders it, on the web and in the mobile app.
- A T2 or T3 decision becomes accepted by merging a pull request. The person named in
  `approved_by` must approve that PR with their own GitHub account. This replaces
  self-declared approval with an authenticated one.
- `gw check` runs on every pull request. Branch protection makes it a gate.
- Archiving agent transcripts is off by default. When it is enabled, the archive lives inside
  `.groundwork/archive/` (gitignored), never elsewhere on the user's machine.
- Users interact through two words, "start" and "end", usually by telling their agent.

## Reasons

- No new infrastructure. Advisors already receive GitHub notifications and can approve on mobile.
- Identity for approvals comes from GitHub authentication.
- The files stay portable. The integration layer can be replaced (for example by GitLab) without data loss.

## Consequences

- Advisors and PIs need (free) GitHub accounts.
- The spec gains §13 (GitHub-native mode) and a `github` field in `ROLES.md`.
- The planned hosted console is deferred: GitHub covers viewing, notification, and approval.
