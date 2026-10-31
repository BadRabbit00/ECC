---
description: Full performance and data-access audit of one component - optimizer in full mode plus db-reviewer - with a ranked list for the plan. Usage /optimize --full <path>
argument-hint: "--full <component path>"
---

# /optimize

Run a whole-component audit. Wave-level checks already happen automatically after each wave; this command is for an on-demand look at everything.

1. Read `$ARGUMENTS`. Without `--full` and a path, answer in Russian with the usage line and stop.
2. Collect the facts the agents need: `docs/SPECIFICATION.md` (load, replicas), `docs/API.md` (hot endpoints), `docs/DATABASE.md` (table classes and sizes). Missing facts → tell the user which ones, and continue with the agents' defaults.
3. Dispatch **in parallel**, read-only:
   - `optimizer`, mode `full`, path from the arguments;
   - `db-reviewer`, mode `diff` with base = the repository's first commit (whole history), scope = the same path.
4. Merge the two reports: drop duplicates (keep the db-reviewer version of data findings), sort by verdict, then priority.
5. Answer in Russian: a short table of `must fix` and the top `suboptimal` items, each with file and fix in one line. If `.plan/PLAN.md` exists, offer to add them to `Follow-ups`; write them only after «да».
