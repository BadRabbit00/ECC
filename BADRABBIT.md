# BadRabbit fork of ECC

This branch (`badrabbit`) is upstream [affaan-m/ecc](https://github.com/affaan-m/ecc)
plus the install module `badrabbit`: a place for skills that exist only in this
fork. Everything else stays byte-identical to upstream so that merging
`upstream/main` is a plain fast-forward with one manifest hunk to re-apply.

The consumer is the NixOS configuration in `BadRabbit00/nixos-conf`
(`home/ai/ecc/`): it takes this branch as the flake input `ecc`, puts the tree
in `/nix/store`, selects modules from `manifests/install-modules.json`
(developer profile + `security` + `devops-infra` + `badrabbit`), rewrites the
docs to run scripts through `ecc-run`, and lays the result out for Claude Code,
Codex and Antigravity. The manifest is the single source of truth for what gets
installed: a skill not listed in a selected module is not installed.

## Adding a skill

1. Create `skills/<name>/SKILL.md` with inline frontmatter:

   ```yaml
   ---
   name: <name>
   description: One line, inline scalar (no `|` block), says when to use it.
   ---
   ```

   `<name>` must match the directory and must not collide with an upstream
   skill or with the skills shipped from `nixos-conf/home/ai/skills` and
   `home/ai/nix-toolkit`.

2. Add `"skills/<name>"` to the `paths` of module `badrabbit` in
   `manifests/install-modules.json`.

3. Validate with the upstream checks (node + repo `node_modules`):

   ```sh
   node scripts/ci/validate-install-manifests.js
   node scripts/ci/validate-skills.js --strict
   node scripts/ci/validate-skill-host-compat.js
   ```

4. Commit, push `badrabbit`, then in `nixos-conf`:

   ```sh
   nix flake update ecc
   nixos-rebuild build --flake .#badrabbitpc   # payload build runs the ECC test-suite
   sudo nixos-rebuild switch --flake .#badrabbitpc
   ```

Scripts inside a skill (`.py`, `.sh`, `.js`) are executed from the store via
`ecc-run`; the copies under `~/.claude/skills` are documentation only, so refer
to them in SKILL.md as `python3 skills/<name>/scripts/x.py` and the Nix payload
rewrites the path.

## Adding an agent or a command

Agents go to `agents/<name>.md` (frontmatter needs `model: sonnet|opus|haiku`
and `tools:` for upstream validators; the Nix payload replaces the model with a
pinned ID from `agentModels` in `home/ai/ecc/payload.nix`, so add the agent
there too or the build fails). Commands go to `commands/<name>.md`. Both are
installed wholesale, no manifest entry needed.

## Syncing with upstream

```sh
git fetch upstream
git merge upstream/main        # or rebase badrabbit onto upstream/main
node scripts/ci/validate-install-manifests.js
git push origin badrabbit
```

New upstream agents must be added to `agentModels` in `nixos-conf` before the
payload builds again.
