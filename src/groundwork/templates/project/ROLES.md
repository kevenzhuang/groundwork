---
principals:
  - id: {{ owner_id }}
    name: "{{ owner_name }}"
    kind: human
    roles: [owner, lead]
    scope: ["*"]
    since: {{ date }}
    git_identity: "{{ owner_git }}"
---

# Roles

Each person or agent in this project, with their roles and scope.
Edit the front-matter above. The text below is for humans.

Rules (spec §1.1):

- There is exactly one `owner`.
- Every agent has a human `sponsor`.
- Agents use their own `git_identity`, never a human's.

To add an agent, append an entry like this:

```yaml
  - id: claude-1
    name: "Claude (coding agent)"
    kind: agent
    roles: [agent]
    scope: ["*"]
    sponsor: {{ owner_id }}
    since: {{ date }}
    git_identity: "claude-agent@users.noreply.example"
```
