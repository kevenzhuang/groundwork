# Rules for AI agents working on this repository

- The spec (`spec/SPEC.md`) is the product. Code implements the spec. Change the spec first
  (via `docs/decisions/` or an RFC), then the code.
- Core commands must work offline and without any AI model (spec principle 8).
- Every check needs a test in `tests/`. Run `pytest -q` before proposing changes.
- Never commit real project data, secrets, or personal information. Fixtures use example.org.
- Commit under your own git identity, with the trailers `Agent:`, `Model:`, `Session:`, `Sponsor:`.
