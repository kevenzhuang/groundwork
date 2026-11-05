# Changelog

Versions follow the spec they implement: tool `0.3.x` implements spec `0.3`.
Entries marked **Action needed** may require changes to your project after `gw upgrade`.

## 0.3.1 (2026-11-05)

- Fix: the `status` job could fail with "non-fast-forward" when two pushes landed close together.
  Status updates now run one at a time (newer pushes cancel older runs), resync with `main`, and retry.
- `gw upgrade` now refreshes the project's workflow file from the current template. Review the diff in
  the upgrade pull request if you had customized it.

## 0.3.0 (2026-11-04)

- **Action needed. Member identity rules (E12).** Each member's `id` must be lowercase letters, digits and
  hyphens (e.g. `arnold-wang`), and every member needs a `name`. Any field that refers to a person
  (`decider`, `approved_by`, `routed_to`, …) must use an `id` from `ROLES.md`, not a display name.
  Run `gw check` after upgrading; each problem comes with a suggested fix.
- New: `aliases` and `orcid` for members; `gw who <name>` finds an id from a name or alias.
- New: GitHub-native mode. `STATUS.md` is generated automatically, approvals are verified against
  pull-request reviews (`gw approvals`), and there is a `gw start` briefing.
- New: prompts and pages follow your language (`language: auto`). Records are never translated.
- New: `gw upgrade`. Projects pin their spec version; newer rules only warn until you upgrade.
- Changed: archiving agent transcripts is opt-in, and archives are kept inside `.groundwork/archive/`.

## 0.2.0 (2026-11-04)

- `gw end` (session capture) and `gw site` (per-audience HTML views).
- Spec 0.2: capture and storage, confidentiality, identity and signing, view templates.

## 0.1.0 (2026-11-04)

- First skeleton: `gw init`, `gw note`, `gw check`; spec 0.1.
