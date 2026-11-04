---
id: "0001"
date: {{ date }}
title: Adopt Groundwork for this project's record
tier: T1
decider: {{ owner_id }}
status: accepted
capture: contemporaneous
classification: internal
---

## Context

This project needs a record that a future reader, human or AI, can follow
without asking the people who did the work.

## Options considered

- No formal record.
- Ad-hoc notes.
- Groundwork.

## Decision

Use Groundwork (spec v{{ spec_version }}).

## Reasons

It uses plain files, works without AI, and is checkable.

## Consequences

Each working session ends with a short capture (`gw end`).
The owner confirms `ROLES.md` and `DECISION-RIGHTS.md`.

## Evidence

- repo:.groundwork/SPEC.md
