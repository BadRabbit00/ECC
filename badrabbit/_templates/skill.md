---
name: example-skill
description: Use when <situation>. Gives <what>. One line, starts with "Use when".
---

<!--
TEMPLATE — copy to badrabbit/skills/<name>/SKILL.md, delete every comment.

A skill is reference material loaded on demand or preloaded into a specific agent via `skills:`.
It may be long, but must be scannable: a table of contents up top, short sections, tables over prose.
Supporting files (tables, examples) may live next to SKILL.md and be referenced by relative path.
Scripts are NOT copied to ~/.claude/skills by the payload; call them through `ecc-run`.
-->

# <Skill title>

## When to use

- <situation>

## Contents

1. [<Section>](#section)

## <Section>

<!-- Reference content. Every recommendation about code has a Bad/Good pair, same format as agents. -->

### R-<AREA>-<NAME> — <short title>

Bad:
```python
# ...
```
Why: <one line>

Good:
```python
# ...
```
