---
description: Find the Nix way to get a tool or library — nixpkgs search, binary provider lookup, option lookup for NixOS/Home Manager, and the exact command to run it without installing (nix shell / nix run) or declare it (devShell / home.packages).
argument-hint: "<tool, library or option name>"
---

# /nix-search

1. `nix search nixpkgs <name>` (and `nix-locate bin/<name>` if the binary name differs from the package).
2. For options: `nixos-option <path>` / `home-manager option <path>` or `nix eval` on the configuration's `options`.
3. Show version and license: `nix eval --raw nixpkgs#<pkg>.version`, `nix eval --json nixpkgs#<pkg>.meta.license`.
4. Answer with three lines: run once (`nix shell nixpkgs#<pkg> -c <cmd>` / `nix run`), declare in a project (`devShells.default.packages`), declare for the user (`home.packages` in `home/programs/default.nix`). Never suggest `pip`, `npm -g`, `cargo install`, `brew` or `nix-env`.
