---
description: Create or fix a project devShell — pinned toolchain from nixpkgs, language env (uv2nix / withPackages / nodejs+pnpm / rust / go), shellHook for .env and sops secrets, direnv .envrc, CI shell. Use when a project lacks flake.nix, when someone wants to pip/npm-install a tool, or when `nix develop` is broken.
argument-hint: "[project path] [language]"
---

# /nix-devshell

1. Read the project: lockfiles (`uv.lock`, `pyproject.toml`, `package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`, `go.mod`), existing `flake.nix`, `.envrc`, CI config.
2. If no flake: scaffold per `nix-flake-patterns` (nixpkgs input, `devShells.default`, `formatter`). Never scaffold over an existing flake; edit it.
3. Toolchain from nixpkgs only: `pkgs.python3`/uv2nix, `pkgs.nodejs_22` + `pkgs.pnpm`, `pkgs.cargo`/`rustc` or rust-overlay, `pkgs.go`, plus linters and LSPs the project uses. The tool the user wanted to install globally goes here.
4. `shellHook`: export project vars, load `.env` if present (`set -a; . ./.env; set +a`), on this machine optionally read `/run/secrets/<name>`. Nothing secret in the flake.
5. `.envrc` with `use flake` (+ `dotenv_if_exists`); `.direnv/` in `.gitignore`; remind to `direnv allow`.
6. Verify: `nix develop -c <toolchain> --version` for each tool, `nix flake check --no-build`.

Report the shell contents, the verification output, and the command the user now runs instead of the global install.
