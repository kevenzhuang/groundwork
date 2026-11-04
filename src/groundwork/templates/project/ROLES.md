---
principals:
  - id: {{ owner_id }}
    name: "{{ owner_name }}"
    aliases: []
    kind: human
    roles: {{ "[owner]" if lead_id else "[owner, lead]" }}
    scope: ["*"]
    since: {{ date }}
{%- if not lead_id %}
    git_identity: "{{ owner_git }}"
{%- endif %}
    github: "{{ owner_github }}"
{%- if lead_id %}
  - id: {{ lead_id }}
    name: "{{ lead_name }}"
    aliases: []
    kind: human
    roles: [lead]
    scope: ["*"]
    since: {{ date }}
    git_identity: "{{ lead_git }}"
    github: "{{ lead_github }}"
{%- endif %}
---

# Roles

Each person or agent in this project, with their roles and scope.
Edit the front-matter above. The text below is for humans.

**Who assigns roles.** The `owner` (usually the PI) has the final say. Any change to this file or to
`DECISION-RIGHTS.md` must be approved by the owner on GitHub; `gw approvals` checks this against
the owner listed *before* the change. New members may propose their own `id` and `name`.

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
