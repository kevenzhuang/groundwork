---
principals:
  - id: {{ owner_id }}
    name: "{{ owner_name }}"
    aliases: []
    kind: human
    roles: [owner, lead]
    scope: ["*"]
    since: {{ date }}
    git_identity: "{{ owner_git }}"
    github: "{{ owner_github }}"
---

# Roles

Each person or agent in this project, with their roles and scope.
Edit the front-matter above. The text below is for humans.

**Identity rules** (spec §3.2):

- `id` is the key every record uses: lowercase letters, digits and hyphens, for example
  `keven`, `arnold-wang`, `gp-li`. It never changes and is never reused.
- `name` is free: any language, any order, for example `庄子钧` or `Zijun "Keven" Zhuang`.
- `aliases` lists other ways people refer to someone, for example `[Arnold, 王老师]`.
  Agents use them; `gw who 王老师` prints the matching `id`.
- `github` is needed to verify approvals. `orcid` is optional and useful for authorship.
- There is exactly one `owner`. Every agent has a human `sponsor` and its own `git_identity`.

To add a member or an agent, append entries like these:

```yaml
  - id: arnold-wang
    name: "Shuoyu (Arnold) Wang"
    aliases: [Arnold, 王老师]
    kind: human
    roles: [advisor]
    github: "arnold-gh"
    orcid: "0000-0000-0000-0000"
  - id: claude-1
    name: "Claude (coding agent)"
    kind: agent
    roles: [agent]
    sponsor: {{ owner_id }}
    git_identity: "claude-agent@users.noreply.example"
```
