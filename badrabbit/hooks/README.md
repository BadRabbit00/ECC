# BR hooks

Deterministic guards for the `br` flavour. Zero tokens until they fire; a denial reaches the model as a one-line reason prefixed `[br-hook]` that says what to do instead.

Python standard library only. Run through the pinned wrapper `br-hook <entry>` (built in `nix/runtime.nix`), which `hooks.json` references as `@BR_HOOK@ <entry>`.

## Entry points

Four entry points instead of one script per rule: every hook call is a process start (~60 ms), and Bash/Edit run constantly.

| Entry | Event · matcher | What it does |
|---|---|---|
| `guard_bash` | PreToolUse · `Bash` | host installs; git rules; destructive commands; secret output; test edits through the shell |
| `guard_write` | PreToolUse · `Edit\|Write\|MultiEdit\|NotebookEdit` | test boundary by `agent_type`; linter/formatter configs closed to executors; task write sets from `.plan/PLAN.md`; orchestrator writes only docs and the plan |
| `guard_read` | PreToolUse · `Read\|Grep` | `.env*` (not `.example`), private keys, age/sops key files |
| `check_written` | PostToolUse · `Edit\|Write\|MultiEdit` | strips BOM and fixes mixed line endings silently; blocks non-UTF-8 and written secrets; compose/Dockerfile advice as context |

Code: `brhooks/common.py` (event, decisions, PLAN.md parser), `bash_checks.py`, `write_checks.py`, `post_checks.py`.

## Who may write what

| Writer | Without `.plan/` | With `.plan/` (orchestrated project) |
|---|---|---|
| main thread (orchestrator) | anything | `docs/**`, `.plan/**`, `README.md`, `CHANGELOG.md`, `CLAUDE.md`, `.claude/rules/**` |
| `test-writer` | only test paths | only `Tests (test-writer)` of tasks with status `red` |
| `coder` | anything except test paths | only `Writes (exclusive)` of tasks with status `green` |
| `refactorer` | anything except test paths | only `Writes (exclusive)` of tasks with status `refactor` |
| `build-fixer` | anything except test paths | same, not limited by the plan |
| `presenter` | `docs/slides/**`, `.plan/PLAN.html` | same |
| any subagent | nothing outside the project (temp dirs are fine) | same |

A test path is any path with a `test`, `tests`, `__tests__`, `e2e`, `integration_test`, or `testdata` directory segment, or a test file name: `test_*.py`, `*_test.py`, `conftest.py`, `*_test.go`, `*_test.dart`, `*.test.{js,jsx,ts,tsx}`, `*.spec.{js,jsx,ts,tsx}`. Our layout uses `tests/` (Flutter/Dart: `test/`); the rest keeps the boundary in existing projects with other conventions.

Parallel executors of the same kind get the union of their tasks' write sets; R-PLAN-WRITESET keeps those disjoint, and the orchestrator's sha256 check of test files is the backstop.

Executors (`coder`, `refactorer`, `build-fixer`, `test-writer`) never edit linter, formatter, type-checker, or coverage configs (`ruff.toml`, `eslint.config.*`, `.golangci.yml`, `mypy.ini`, `.coveragerc`, …). `[tool.ruff]` inside `pyproject.toml` is not caught; review is the backstop.

## Git

Free on any branch except `main`, `master`, `develop`.

- On develop/main: no commit, add, reset, rebase, cherry-pick, revert, am, apply, pull (except `--ff-only`), merge.
- The one write to develop: `git merge [--no-ff] feature/…` (or `hotfix/…`), plus `merge --abort`.
- Never: push develop/main (including `HEAD` while on them, `--all`, `--mirror`, `--tags`), delete or force-move them, `--no-verify`, `git clean -x`.

## Upstream ECC hooks

The br flavour installs **none** of the 27 upstream hooks. Every hook is a process start on every matching tool call, and several inject text into the context.

| Upstream hook | Decision | Why |
|---|---|---|
| `pre:config-protection` | ported into `guard_write` | useful; narrowed to executors |
| `pre:bash:dispatcher` (quality, tmux, push, GateGuard) | dropped | git/push rules are in `guard_bash`; the rest is upstream workflow |
| `pre:edit-write:gateguard-fact-force`, `pre:powershell:*` | dropped | forces questions on first edit: tokens on every file; PowerShell is not used |
| `pre:write:doc-file-warning` | dropped | docs-kit defines the docs layout; `docs.md` rule covers it |
| `pre:edit-write:suggest-compact`, `pre:compact` | dropped | adds context; the plan file is the durable state |
| `pre:observe:continuous-learning`, `stop:evaluate-session` | dropped | logs every tool call; "learn once" lives in core CLAUDE.md |
| `pre:governance-capture` | dropped | off upstream by default; secrets are covered by `guard_*` and `check_written` |
| `pre:mcp-health-check`, `post:mcp-health-check` | dropped | subagents have no MCP; main session handles failures itself |
| `pre/prompt/stop:hookify-runtime` | dropped | no Hookify rules in Alexey's projects |
| `session:start`, `stop:session-end`, `session:end:marker` | dropped | loads previous context into every session = tokens |
| `session-start/stop:plan-canvas-*` | dropped | Plan Canvas is not used; `.plan/` replaces it |
| `post:dispatcher:sync/async` | dropped | upstream formatters/console.log checks; executors run linters through `nix develop -c` |
| `stop:format-typecheck`, `stop:check-console-log` | dropped | JS-only, runs Biome/Prettier from the host |
| `stop:cost-tracker` | dropped for now | stage 10 measures tokens with `/context` and transcripts; revisit if needed |
| `stop:desktop-notify` | dropped | macOS/WSL only |
| `post:skill:track` | dropped | Skill tool is off in subagents |

## Limits (by design)

- Bash checks read the command text. They catch mistakes, not a determined bypass (a script that writes into `tests/` passes). Backstops: sha256 of test files in PLAN evidence, code review.
- A hook that crashes exits 1: Claude Code shows the error and the tool call proceeds (fail-open). The tests below are what keeps them correct.

## Tests

```bash
cd badrabbit/hooks && python3 -m unittest discover -s test -t test
```
