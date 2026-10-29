---
name: nix-debugging
description: "Diagnosing Nix failures from the error text: evaluation errors (infinite recursion, attribute missing, conflicting definitions, path does not exist), build failures (nix log, --keep-failed, breakpointHook), hash mismatches, IFD and impurity complaints, sandbox and HOME problems, slow evaluations, closure bloat (nix why-depends, nix-tree, path-info), and broken activations. Use when a nix command fails and the cause is not obvious from the first line."
---

# Debugging Nix

## First moves, always

1. Re-run with `--show-trace` (eval errors) or `-L` (build errors). Read the **last** `error:` block first; the ones above are usually context.
2. For a failed derivation the message names the `.drv`; `nix log <that>` prints the full build log.
3. `git status`: an untracked new file is the most common "path does not exist".

## Evaluation errors

| Error | Cause and fix |
|---|---|
| `path '/nix/store/…-source/foo.nix' does not exist` | file not `git add`ed, or wrong relative path. `git add`, check `./` prefix. |
| `attribute 'x' missing` | typo, wrong nixpkgs rev (package renamed), or using `pkgs.x` where it is `pkgs.python3Packages.x`. `nix search nixpkgs x`, check `nix eval nixpkgs#x`. |
| `infinite recursion encountered` | `config` used to compute `imports`, or `if` on `config.*` at module top level instead of `lib.mkIf`, or `rec` attrset referencing itself. Move the condition under `config = lib.mkIf …`. |
| `The option 'x' is defined multiple times` / conflicting definitions | two modules set a non-mergeable option. `nix eval '.#…options.x.definitionsWithLocations'`, then `mkDefault` on one side or `mkForce` with a comment. |
| `The option 'x' does not exist` | option renamed in the new nixpkgs/HM (check release notes), module not imported, or typo. `nixos-option x`, `home-manager option x`. |
| `cannot coerce a set to a string` | you interpolated a package attrset without `${lib.getExe pkg}` / `${pkg}/bin/x`, or an option that is a submodule. |
| `access to absolute path '/…' is forbidden in pure evaluation mode` | `builtins.readFile "/etc/…"` or `/home` path in a flake. Pass the data as an input, or `--impure` with justification. |
| `error: getting status of '/nix/store/…'` after `nix flake update` | an input's hash changed upstream (force-pushed tag). Pin to a `rev`. |
| string `'…' has context with the output 'out'` when `nix build`ing a path string | you asked to build a string, not a derivation. Build the derivation and append the subpath yourself. |

Interactive: `nix repl` → `:lf .` → `:p nixosConfigurations.badrabbitpc.config.services.foo` with tab completion; `builtins.trace`/`lib.traceValSeq` in the expression.

## Build failures

| Symptom | Fix |
|---|---|
| `hash mismatch in fixed-output derivation` | copy `got:` into the expression; check you used the fetcher whose hash semantics match (`fetchurl` file vs `fetchFromGitHub` tree). |
| `command not found` inside build | missing `nativeBuildInputs`; for `#!/usr/bin/env` shebangs run `patchShebangs`. |
| `/usr/bin/env: No such file`, `HOME` not writable | sandbox. `patchShebangs`, `export HOME=$TMPDIR` in the phase. |
| network access during build (`Could not resolve host`) | the build downloads (npm, pip, cargo). Use the lockfile builders (`buildNpmPackage`, `importNpmLock`, `cargoHash`, uv2nix) so fetching is a fixed-output step. |
| `EOVERRIDE` / `ENOTCACHED` with importNpmLock | `overrides`/`devDependencies` in package.json conflict with the rewritten lock; feed a trimmed `package` and prod-only `packageLock` (see `home/ai/ecc/default.nix`). |
| `RPATH of binary … contains a forbidden reference to /build` | a path to `$TMPDIR` baked into the output; move the file into `$out` and reference that. |
| tests fail only in sandbox | time zone, locale, `HOME`, `/dev/kvm`, no network. Skip those specific tests with a named comment. |
| build takes forever / machine swapping | you forgot `--max-jobs 4 --cores 4`; check `nix build --dry-run` for a monster (chromium, LLVM, CUDA) that should come from a substituter: `nix show-config | grep substituters`. |

Tools: `nix build --keep-failed` keeps `/tmp/nix-build-<name>` for inspection; `breakpointHook` in `nativeBuildInputs` pauses the build and prints a `cntr attach` command; `nix build --rebuild` to check reproducibility; `nix-diff drvA drvB` to see why a rebuild happened.

## Closure and dependency questions

- "Why is X in my system closure": `nix why-depends /run/current-system nixpkgs#X` (or `.#nixosConfigurations.badrabbitpc.config.system.build.toplevel`).
- "What is big": `nix path-info -Sh result`, `nix-tree result` (sort by closure size with `s`), `nix path-info -rSh result | sort -hk2 | tail`.
- "What changed between generations": `nvd diff /nix/var/nix/profiles/system-<n>-link /nix/var/nix/profiles/system-<m>-link`.
- "Who keeps this path alive from GC": `nix-store --query --roots <path>`.

## Slow evaluation

- `nix eval --json .#<attr> --trace-verbose` is not a profiler; instead `NIX_SHOW_STATS=1 nix eval …` for allocation stats, and bisect by evaluating sub-attributes.
- Usual suspects: IFD (`importJSON "${drv}/…"`, `builtins.readFile` of a derivation), `builtins.fetchTarball` without `sha256`, huge `lib.filterAttrs` over `pkgs`, `nixpkgs` imported more than once (check `nix flake metadata` for duplicate nixpkgs nodes).

## Activation and runtime

- `home-manager`/NixOS activation fails on "would overwrite existing file": a file HM wants to link exists unmanaged. Move it away (back it up), never delete blindly.
- A program ignores its config after switch: it writes its own config and the HM symlink broke the write. Switch to an activation merge (see `nixos-module-patterns`).
- Service fails after switch: `journalctl -u <unit> -b -e`, `systemd-analyze verify`, compare `nvd diff`.
- Boot problems: previous generation from the bootloader menu, then `journalctl -b -1 -p err`. In this repo, udev `chmod` on sysfs driver dirs once broke coldplug with EIO; `udevadm trigger --dry-run --type=all` shows enumeration failures.

## Report format

State the failing command, the decisive error line, the root cause in one sentence, the fix, and the verification command you re-ran. If you changed a hash, say which fetcher and which rev.
