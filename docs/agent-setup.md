# Groundwork: setup and daily use (instructions for AI agents)

You are an AI coding agent (Claude Code, Codex, or similar). A human asked you to use Groundwork
for the current project. Follow these steps. Speak to the human in their language. Keep it short:
the human should not have to learn commands or concepts.

## A. One-time setup

1. **Check the project.** It must be a git repository with a GitHub remote. If it is not, explain
   this in one sentence and offer to set it up.
2. **Install the tool** if `gw` is not available:
   `pipx install git+https://github.com/kevenzhuang/groundwork` (or `pip install --user ...` if pipx is missing).
3. **Ask the human three things, together in one message:**
   - the project title;
   - a short id for themselves (for example `keven`);
   - their GitHub login.
4. **Initialize on a new branch:**
   ```
   git checkout -b groundwork-setup
   gw init . --title "<title>" --owner <id> --owner-name "<name>" --github <login>
   ```
   `gw init` never overwrites existing files.
5. **Register yourself as an agent** in `ROLES.md`:
   - your own `id`;
   - `kind: agent`;
   - `sponsor: <human id>`;
   - your own `git_identity`. Never use the human's identity.
6. **Fill in `PROJECT.md`** from what you can see in the repository: goal, current state, milestones.
   Mark anything you inferred with "(draft — please confirm)".
7. Run `gw check`, commit, push the branch, and open a pull request titled "Set up Groundwork".
8. **Tell the human, in about three lines:**
   - Merge the pull request.
   - In GitHub → Settings → Branches, protect `main` and require the `groundwork` check.
     If `STATUS.md` updates are blocked, allow GitHub Actions to bypass the rule.
   - Invite the advisor and PI as collaborators, then add them to `ROLES.md` with their `github` logins.
     You can do the `ROLES.md` part for them once they give you the logins.

## B. When the human says "start" (开工)

1. Run `gw start --as <human id>`.
2. Summarize the result in 3–5 lines: where things stand, what is blocked, what is next,
   and anything waiting for them (decisions, questions).

## C. When the human says "end" (收工)

1. Run `gw end --preview` to see what changed since the last session. It writes nothing.
2. **Ask the human only what you cannot tell from the evidence**, a few questions at a time:
   - why each change was made, grouped by folder if there are many;
   - what they were thinking or trying;
   - what is blocked;
   - what comes next;
   - anything relied on that isn't verified.

   If an answer is vague, ask one follow-up question. Never invent answers.
   If they say something is confidential, write `[withheld: <category>; ask <id>]` instead.
3. Write their answers to a temporary YAML file with the keys
   `did, thinking, blocked, next, unverified, reasons: {path: reason}`.
   Then run `gw end --as <your agent id> --answers <file>`.
4. Show them the result in a few lines and ask "Is this accurate?"
   - If they say yes, set `confirmed_by: <human id>` in that session file.
   - Then commit and open (or update) a pull request. Merging it is their authenticated confirmation.

## D. Decisions

When something changes direction (method, scope, venue, authorship, public release):

- Write `decisions/NNNN-<slug>.md` as a **T0 proposal** (`status: proposed`, `proposed_by: <your id>`).
- Open a pull request and request review from the person `DECISION-RIGHTS.md` names for that area.
- Never set `decider` or `approved_by` yourself. Only the human, through their GitHub review, makes it accepted.

## Never

- Set `human-verified`, `verified_by`, `approved_by`, or act as `decider`.
- Edit past decisions, sessions, or handoffs. Add new entries instead.
- Write secrets.
- Push to `main` directly when branch protection exists.
