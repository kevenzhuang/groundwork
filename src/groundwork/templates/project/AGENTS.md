# Rules for AI agents

This project keeps its record with Groundwork. The full spec is at
`.groundwork/SPEC.md`; read §5 before working.

1. At the start of a session, read `PROJECT.md`, the latest file in `sessions/`,
   and any open questions routed to your sponsor. Then summarize your
   understanding in 3–5 lines.
2. Never set `human-verified`, `verified_by`, `approved_by`, or act as `decider`.
   Write decision-like changes as T0 proposals in `decisions/`.
3. Never edit or delete past decisions, sessions, or handoffs. Add new entries instead.
4. Cite evidence for every claim you add to the record, or mark it `unverified`.
5. Never write secrets. Don't copy `restricted` content. Skip items with `ai_allowed: false`.
6. Commit under your own git identity, with the trailers
   `Agent:`, `Model:`, `Session:`, `Sponsor:`.
7. At the end of a session, run `gw end` (or follow spec §8) and ask the human
   only what the evidence can't answer.
8. Run `gw check` before proposing changes.
