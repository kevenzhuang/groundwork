---
id: "0001"
date: 2026-11-04
title: Founding decisions: name, license, visibility, positioning
tier: T3
decider: keven
approved_by: keven
status: accepted
capture: contemporaneous
---

## Context

Groundwork began as a way to keep one research project's record usable across people and
AI agents. It grew into a general, project-agnostic standard.

## Decisions

1. **Name.** The product is Groundwork. The PyPI package is `groundwork-lab`, because
   `groundwork` is already taken. The CLI is `gw`, with `groundwork` as an alias.
2. **Licenses.** Code is under Apache-2.0, chosen for its patent grant, which institutions
   accept. The spec is under CC-BY-4.0, so it can spread with attribution.
3. **Visibility.** The repository is public from day one. Consequence: no data from any
   real project ever enters this repository.
4. **Positioning.** Groundwork is a neutral, open standard: "a lab notebook for AI-era research".
   It does not lead with an AI-disclosure feature. Disclosure is one possible use of the
   record, not the headline.
5. **First pilot.** One real project, with light use during Phase 1.

## Reasons

These choices are recorded in the planning document "Architecture & Roadmap v1"
(2026-11-04), kept outside this repository.

## Evidence

- The PyPI name `groundwork` is held by an unrelated, dormant project (checked 2026-11-04).
