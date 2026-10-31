# badrabbit/ — BR-ECC

Our own layer on top of upstream ECC. Everything Claude Code loads in the "br" flavour comes from
this directory, plus a short allowlist of upstream/fork files (see `allowlist.json`).
Upstream files are never edited, so `git merge upstream/main` stays cheap.

Language: everything in this directory is **English** (cheaper in tokens, models follow it more precisely).
Everything the agents say **to the user** is **Russian** — that is stated in the output style and the subagent contract.

## Layout

```
badrabbit/
├── README.md                    # this file
├── allowlist.json               # fork/upstream agents, skills, commands that the br payload also installs
├── agent-models.json            # pinned model + effort per br agent (payload writes them into frontmatter)
├── settings.fragment.json       # merged into ~/.claude/settings.json (env, outputStyle)
├── core/
│   ├── CLAUDE.md                # always-on core for the MAIN session → ~/.claude/CLAUDE.md
│   └── subagent-contract.md     # injected by the payload into EVERY br agent right after its frontmatter
├── output-styles/
│   └── orchestrator.md          # the orchestrator; main session only, subagents never see it
├── agents/                      # br subagents → ~/.claude/agents/
├── rules/                       # path-scoped rules → ~/.claude/rules/br/
├── skills/                      # br skills → ~/.claude/skills/
├── hooks/                       # hook scripts (Python) + hooks.json + tests
├── templates/                   # PLAN.md, POLICY.defaults.md, slides.html — used by the orchestrator
├── tools/
│   ├── validate.py              # structural checks; runs inside the payload build
│   ├── validate.json            # limits and exemptions for validate.py
│   └── test_validate.py
└── _templates/                  # how to write an agent / rule / skill — NOT installed
```

## How knowledge is layered

| Layer | Loaded | Where | Budget |
|---|---|---|---|
| Core | every main-session request | `core/CLAUDE.md` | ≤ 150 lines |
| Subagent contract | every br subagent | `core/subagent-contract.md`, injected at build time | ≤ 40 lines |
| Path rules | when the agent touches matching files | `rules/*.md` with `paths:` | ≤ 120 lines each |
| Agent body | when that agent runs | `agents/*.md` | ≤ 300 lines each |
| Skills | on demand / preloaded by name | `skills/*/SKILL.md` | no hard limit, keep it scannable |
| Hooks | never in context | `hooks/` | 0 tokens |

Rule of thumb: if a machine can check it, it is a hook, not text.
If only one agent needs it, it lives in that agent, not in a rule.

## Subagent isolation (why agents are cheap)

Every br agent frontmatter MUST have:

```yaml
omitClaudeMd: true                     # no ~/.claude/CLAUDE.md, no project CLAUDE.md, no unscoped rules
tools: <explicit allowlist>            # only what the role needs
disallowedTools: Agent, Skill, mcp__*  # no nested subagents, no free skill browsing, no MCP schemas
maxTurns: <n>                          # hard stop for runaway loops
```

Path-scoped rules from `~/.claude/rules/br/` still load for these agents when they touch matching files.
Skills an agent really needs are preloaded by name in `skills:`.
Nested subagents are also disabled globally: `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` in `settings.fragment.json`.

## Examples are mandatory

An instruction without an example is air. Every rule about code — in an agent or a path rule — has a pair:

````markdown
### R-DB-PAGINATION — paginate in the query, never in memory
Bad:
```python
rows = (await session.scalars(select(Order))).all()
return rows[offset:offset + limit]
```
Why: loads the whole table into the process on every page request.

Good:
```python
stmt = select(Order).order_by(Order.id).where(Order.id > after_id).limit(limit)
return (await session.scalars(stmt)).all()
```
````

- The heading starts with a rule id: `R-<AREA>-<NAME>`. Ids let reviewers cite rules in findings.
- `Bad:`, then `Why:` (one line), then `Good:`. Code blocks carry a language tag.
- `validate.py` fails the build if an agent or rule has no `Bad:`/`Good:` pair. The exemptions are in `validate.json`.

## Naming

- Agents: kebab-case, role name, no prefix: `test-writer`, `db-reviewer`. The file name equals `name:`.
- Rules: `<topic>.md`: `python.md`, `db.md`, `auth.md`.
- Skills: `skills/<name>/SKILL.md`, and `name:` equals the directory.
- Hooks: `guard_*.py` deny before a tool call. `check_*.py` warn after it. `fix_*.py` repair after it.
- Rule ids: `R-<AREA>-<NAME>`, upper-case, unique across the repo. `validate.py` checks uniqueness.

## Adding something

1. Copy the matching file from `_templates/` and fill it in.
2. For an agent, add its model and effort to `agent-models.json`.
3. Run `nix develop -c python3 badrabbit/tools/validate.py badrabbit` (it also runs inside `nix build .#ecc-payload-br`).
4. Build `nix build .#ecc-payload-br` and inspect `result/claude/`.
