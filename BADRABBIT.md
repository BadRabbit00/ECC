# BadRabbit fork of ECC

Branch `badrabbit` = upstream [affaan-m/ecc](https://github.com/affaan-m/ecc)
plus everything that used to live in `BadRabbit00/nixos-conf/home/ai/{ecc,nix-toolkit,ask-models}`:

| Where | What |
| --- | --- |
| `nix/runtime.nix` | repo + `node_modules` in `/nix/store`, wrappers `ecc-run` (skill scripts) and `ecc-hook` (Claude Code hooks) with pinned node/python/bash/git, hook profile and disabled hooks |
| `nix/payload.nix` | module selection from `manifests/install-modules.json`, excluded skills, pinned model/effort per agent for Claude, Codex and Antigravity (`agentModels`), docs rewritten to call scripts through `ecc-run`, Nix-doctrine banner in every skill/command/agent, Codex roles and prompts, agy agents, `hooks.json` for `settings.json` |
| `nix/nix-first.md`, `nix/ECC-GUIDE.md` | always-on Nix rule and the command guide shipped to `~/.claude` |
| `nix/default.nix`, `flake.nix` | `lib.mk { pkgs }` for consumers, packages `ecc`, `ecc-run`, `ecc-hook`, `ecc-payload`, devShell for the upstream validators |
| `agents/nix-*.md` | nix-architect, nix-engineer, nix-reviewer, nix-build-resolver, nix-test-runner |
| `commands/nix-*.md`, `commands/ask-*.md`, `commands/write-*.md` | Nix toolkit commands; second-opinion and delegated-writing commands (the `ask-*`/`write-*` binaries themselves stay in nixos-conf) |
| `skills/nix-*`, `skills/nixos-module-patterns`, `skills/project-flake` | own skills, listed in install module `badrabbit` |

Upstream files are untouched except `manifests/install-modules.json`,
`manifests/install-profiles.json` (module `badrabbit`) and the regenerated
digest in `manifests/context-packs/skill-triggers@1.json`, so `git merge
upstream/main` stays cheap.

## How it is consumed

`nixos-conf` has the flake input `ecc = github:BadRabbit00/ECC/badrabbit` and
calls `inputs.ecc.lib.mk { inherit pkgs; }`; `home/ai/ecc/default.nix` there
only lays the payload out into `~/.claude`, `~/.codex`, `~/.gemini/config` and
merges `hooks.json` into `~/.claude/settings.json`. The manifest is the single
source of truth: a skill not listed in a selected module
(`developer` profile + `security` + `devops-infra` + `badrabbit`) is not installed.

## Adding a skill

1. `skills/<name>/SKILL.md` with inline frontmatter (`name:` equal to the
   directory, one-line `description:`, no `|` block scalars). The name must not
   collide with upstream skills or with `nixos-conf/home/ai/skills`.
2. Add `"skills/<name>"` to module `badrabbit` in `manifests/install-modules.json`.
3. Scripts inside the skill (`.py`, `.sh`, `.js`) run from the store through
   `ecc-run`; write them in SKILL.md as `python3 skills/<name>/scripts/x.py`
   and the payload rewrites the path. Copies under `~/.claude/skills` carry no
   scripts on purpose.
4. Validate in the devShell (direnv loads it, or `nix develop`):

   ```sh
   node scripts/ci/validate-install-manifests.js
   node scripts/ci/validate-skills.js --strict
   node scripts/ci/validate-context-profiles.js   # stale digest -> see below
   nix build .#ecc-payload                        # runs the upstream hook tests too
   ```

   Adding or removing a skill changes the skill registry digest; refresh
   `registryDigest` in `manifests/context-packs/skill-triggers@1.json` with
   the value printed by `node nix/registry-digest.js .` (the upstream generator
   needs an LLM login; the triggers themselves do not change).

5. Commit, push `badrabbit`, then in `nixos-conf`: `nix flake update ecc`,
   `nixos-rebuild build --flake .#badrabbitpc`, `sudo nixos-rebuild switch`.

## Adding an agent or a command

Agents: `agents/<name>.md` with `model: sonnet|opus|haiku` and `tools:` (upstream
validator), plus an entry in `agentModels` in `nix/payload.nix` with the pinned
Claude/Codex/agy models, or the payload build fails on purpose. Commands:
`commands/<name>.md`; add Claude-only ones to `codexExcludedCommands`.

## Syncing with upstream

```sh
git fetch upstream && git merge upstream/main
node scripts/ci/validate-install-manifests.js
nix build .#ecc-payload     # new upstream agents must be added to agentModels
git push origin badrabbit
```
