---
confirmed_by:
confirmed_on:
areas:
  - area: daily-work
    examples: "reading, screening sources, code, plots, parameter sweeps"
    tier: T1
    approver_role:
    veto_window:
  - area: method-and-scope
    examples: "change approach, add/drop a contribution, change dataset"
    tier: T2
    approver_role: advisor
    veto_window: 3d
  - area: writing-structure
    examples: "restructure paper or report, change framing"
    tier: T2
    approver_role: advisor
    veto_window: 3d
  - area: publication
    examples: "target venue, submission date, authorship list and order"
    tier: T3
    approver_role: owner
  - area: public-release
    examples: "publish data, code, or a view of this record"
    tier: T3
    approver_role: owner
  - area: resources
    examples: "money, shared compute, lab equipment"
    tier: T3
    approver_role: owner
  - area: external
    examples: "contact sponsors or companies, talks, press"
    tier: T3
    approver_role: owner
  - area: people-and-handoff
    examples: "add a member, hand over a role"
    tier: T3
    approver_role: owner
  - area: verification
    examples: "mark an item human-verified"
    tier: T1
    approver_role:
  - area: rules
    examples: "change this file or ROLES.md"
    tier: T3
    approver_role: owner
---

# Decision rights

This file says who may decide what (spec §1.2 and §3.3).
It is a default template. Adjust the areas, then have the owner confirm it by
filling in `confirmed_by` and `confirmed_on` and recording a decision.

- **T0**: agents may only propose.
- **T1**: decide and log.
- **T2**: decide, notify the approver role, and wait for the veto window. Silence counts as consent.
- **T3**: ask first.

If unsure, use T2.
