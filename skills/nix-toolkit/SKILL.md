---
name: nix-toolkit
description: "Map of the Nix tool ecosystem and the exact command for each job: search, evaluate, build, run, develop, update inputs, inspect closures and dependencies, diff generations, format, lint, fetch hashes, garbage-collect, LSP. Use whenever a Nix task needs a tool and you are not sure which one, or when a task is being done with a bare `nix build` where a better tool exists."
---

# Nix toolkit: which tool for which job

All tools below are either part of `nix` itself or available as `nix shell nixpkgs#<tool> -c <tool> …`. On this machine the lint/format/inspect set is already in `home.packages` (see `home/ai/nix-toolkit/default.nix`).

## Search and discover

| Need | Command |
|---|---|
| Find a package | `nix search nixpkgs <name>` (regex, case-insensitive); `nix search nixpkgs --json <name> \| jq` for scripting |
| Which package ships a binary or file | `nix-locate bin/<name>` (needs `nix-index` db: `nix-index` once, slow); fallback `nix search nixpkgs <name>` |
| Run a binary once without installing | `nix run nixpkgs#<pkg> -- <args>` or `, <cmd>` (comma, uses nix-index) |
| Package metadata | `nix eval nixpkgs#<pkg>.meta --json \| jq '{description,homepage,license}'`, `nix eval --raw nixpkgs#<pkg>.version` |
| NixOS option docs | `nixos-option <path>`; `nix eval '.#nixosConfigurations.badrabbitpc.options.<path>.description'`; search.nixos.org for the web view |
| Home Manager option docs | `home-manager option <path>` or `nix eval '.#nixosConfigurations.badrabbitpc.config.home-manager.users.BadRabbit.<path>'` |
| Which nixpkgs rev a flake pins | `nix flake metadata . --json \| jq '.locks.nodes.nixpkgs.locked.rev'` |

## Evaluate and inspect expressions

| Need | Command |
|---|---|
| Evaluate an attribute | `nix eval .#<attr>`, `--json`, `--raw`; `--apply 'x: builtins.attrNames x'` to list keys |
| Interactive exploration | `nix repl` then `:lf .` (load flake), `:p <expr>` (print deep), `:b <drv>` (build), `:e <attr>` (edit source), `:doc <fn>` |
| Where an option is set | `nix eval '.#nixosConfigurations.badrabbitpc.options.<path>.definitionsWithLocations' --json` |
| Trace an eval error | add `--show-trace`; `builtins.trace` / `lib.traceVal` in code; `lib.debug.traceSeq` |
| Check syntax only | `nix-instantiate --parse <file>` |
| Dependency tree of a derivation | `nix-tree .#<attr>` (TUI), `nix-tree --derivation` for build-time deps |
| Why does A depend on B | `nix why-depends .#<attr> nixpkgs#<pkg>`; add `--all` for every path, `--derivation` for build-time |
| Closure size | `nix path-info -Sh .#<attr>` (closure), `-sh` (self only), `--closure-size --json` |
| Compare two derivations | `nix-diff <drvA> <drvB>` (what changed in the build), `nvd diff <storeA> <storeB>` (what changed in a closure, e.g. two system generations) |
| Compare generations | `nvd diff /run/current-system result` after `nixos-rebuild build`; `nix profile diff-closures --profile /nix/var/nix/profiles/system` |

## Build, run, develop

| Need | Command |
|---|---|
| Build an output | `nix build .#<attr> -L --max-jobs 4 --cores 4` (`-L` streams logs, `--no-link` skips `result`, `--print-out-paths` prints paths) |
| Build with a progress TUI | `nom build .#<attr>` (nix-output-monitor); `nixos-rebuild build --flake .#badrabbitpc \|& nom` |
| Dry run: what would be built or downloaded | `nix build --dry-run .#<attr>` |
| Build the NixOS system without switching | `nixos-rebuild build --flake .#badrabbitpc` then `nvd diff /run/current-system result` |
| Test-switch until reboot | `sudo nixos-rebuild test --flake .#badrabbitpc` (no bootloader entry); `switch` makes it permanent; `boot` applies on next boot |
| Build the HM user layer only | `nix build --impure --expr '(builtins.getFlake (toString ./.)).nixosConfigurations.badrabbitpc.config.home-manager.users.BadRabbit.home.activationPackage'` and `<result>/activate` |
| Standalone HM (Arch target) | `nix build --impure '.#homeConfigurations."badrabbit@ARCH-BOX".activationPackage'` |
| Enter a devShell | `nix develop`, `nix develop -c <cmd>`, `nix develop .#<shell>`; `direnv allow` with `use flake` in `.envrc` |
| One-off tool | `nix shell nixpkgs#<pkg> -c <cmd>`; several: `nix shell nixpkgs#a nixpkgs#b -c …` |
| Run a flake app | `nix run .#<app> -- <args>` |
| Rebuild a derivation ignoring cache | `nix build --rebuild .#<attr>` (checks reproducibility) |
| Keep the failed build dir | `nix build --keep-failed` then inspect `/tmp/nix-build-*`; or add `breakpointHook` to `nativeBuildInputs` and `cntr attach` |
| Build log of a failed derivation | `nix log <drv-or-out-path>` (printed in the error), `nix log .#<attr>` |

## Inputs, locks, updates

| Need | Command |
|---|---|
| Update all inputs | `nix flake update` |
| Update one input | `nix flake update <input>` (new CLI) or `nix flake lock --update-input <input>` (old) |
| Pin an input to a rev | `nix flake lock --override-input nixpkgs github:nixos/nixpkgs/<rev>` |
| Show inputs and revs | `nix flake metadata .` |
| Check a flake evaluates and `checks` pass | `nix flake check` (`--no-build` for eval only, `-L` for logs) |
| Show outputs | `nix flake show .` (`--json` for scripting, `--all-systems`) |
| Fetch a source hash | `nix flake prefetch github:<owner>/<repo>/<rev> --json \| jq -r .hash`; `nurl https://github.com/<o>/<r> <rev>` prints the full fetcher call; `nix-prefetch-git`, `nix-prefetch-url --unpack <url>` |
| Hash of a file or URL | `nix hash file <path>`, `nix hash to-sri sha256:<hex>`, `nix-prefetch-url <url>` |
| Bootstrap a package from a repo | `nix-init` (interactive, detects language builders) |
| Test a nixpkgs PR locally | `nixpkgs-review pr <number>` |

## Format, lint, LSP

| Need | Command |
|---|---|
| Format | `nixfmt <files>` (RFC style, the nixpkgs standard); `nix fmt` if the flake defines a formatter |
| Lint anti-patterns | `statix check .` (`statix fix` applies safe fixes) |
| Dead code | `deadnix .` (`deadnix -e` edits in place) |
| Editor LSP | `nil` or `nixd` in the editor config; `nixd` understands NixOS/HM options when given the flake |
| Validate compositor config in this repo | `niri validate --config home/desktop/niri/config.kdl` (mandatory before rebuild when niri config changed) |

## Store, profiles, cleanup

| Need | Command |
|---|---|
| Garbage collect | `nix-collect-garbage` (user), `sudo nix-collect-garbage -d` (also deletes old generations), `--delete-older-than 14d` |
| Deduplicate the store | `nix store optimise` (or `nix.settings.auto-optimise-store = true`) |
| Verify store integrity | `nix store verify --all`, `nix store repair <path>` |
| List system generations | `sudo nix-env --list-generations -p /nix/var/nix/profiles/system`; HM: `home-manager generations` |
| Roll back | `sudo nixos-rebuild switch --rollback`; or boot the previous entry |
| GC roots keeping something alive | `nix-store --query --roots <path>`; `nix-store --gc --print-roots` |
| Who references a path | `nix-store --query --referrers <path>` |
| Check substituters before a long build | `nix show-config \| grep -E 'substituters|trusted-public-keys'`; `nix build --dry-run` shows what will be fetched vs built |

## Secrets and env

| Need | Command |
|---|---|
| Edit a sops file | `sops secrets/<file>.yaml` (keys from `.sops.yaml`) |
| Rotate keys | `sops updatekeys secrets/<file>.yaml` |
| Decrypted runtime path on NixOS | `/run/secrets/<name>` (owner and mode from `sops.secrets.<name>`) |
| Project env | `.envrc` with `use flake` + `dotenv_if_exists`; never commit `.env` |

## Rules of thumb

- Prefer `nix build --dry-run` and `nvd diff` before any `switch`: know what changes.
- `-L` on anything that compiles; `nom` when you want to see the graph.
- Throttle: `--max-jobs 4 --cores 4` for C++/CUDA/Rust monsters. Never `--max-jobs auto` on them.
- IFD (`builtins.readFile` of a derivation output at eval time, `importJSON "${src}/…"`) is allowed only when there is no alternative; it slows every evaluation.
- Add new files with `git add` before evaluating a flake, otherwise "path does not exist".
