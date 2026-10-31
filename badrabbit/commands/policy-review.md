---
description: Review the project's docs/POLICY.md - list defaults the user has not confirmed, policies missing compared with the current defaults, and ask for confirmation in one table. Usage /policy-review
---

# /policy-review

1. Read `docs/POLICY.md` and `~/.claude/br/templates/POLICY.defaults.md`. If `docs/POLICY.md` does not exist, say so and offer to create it from the defaults (stage 3 of the flow); stop.
2. Build three lists:
   - **unconfirmed**: policies with `Source: default (P-…)`;
   - **missing**: `P-*` policies in the defaults that apply to this project (by its stack and services) but are absent from `docs/POLICY.md`;
   - **drifted**: policies whose value differs from the current default while `Source` is still `default` (the defaults changed since they were copied).
3. Show one table in Russian: policy id, what it says in one line, the value now, the default, and «оставляем?». `Ask: yes` policies first, with the default pre-selected. Ask through `AskUserQuestion` when there are at most 4 forks; otherwise a numbered list with defaults.
4. After the answers, update `docs/POLICY.md` (you may write docs): new values, `Source: confirmed YYYY-MM-DD`, added policies. Report what changed in three lines.
