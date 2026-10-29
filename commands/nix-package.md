---
description: Package a program or library with Nix — pick the right builder (mkDerivation, buildNpmPackage/importNpmLock, buildPythonApplication/uv2nix, rustPlatform, buildGoModule), fetch and pin the source hash, wire tests, add meta, expose it as packages.<name> or in an overlay.
argument-hint: "<repo URL or path> [version]"
---

# /nix-package

1. Check nixpkgs first: `nix search nixpkgs <name>`; if it exists, prefer it (possibly with `overrideAttrs`) and stop.
2. Inspect the source: language, build system, lockfiles, tests. `nix-init` may draft the expression; review everything it produces.
3. Write `nix/<name>.nix` with `callPackage` signature per the `nix-packaging` skill: pinned `rev`/`tag`, SRI hash from `nix flake prefetch … --json | jq -r .hash` or the fake-hash build, `nativeBuildInputs` vs `buildInputs`, `doCheck`, `meta` with `license` and `mainProgram`.
4. Expose: `packages.<system>.<name> = pkgs.callPackage ./nix/<name>.nix { }` (project) or an overlay file (this repo: `overlays/`).
5. Build: `nix build .#<name> -L --max-jobs 4 --cores 4`; check `nix path-info -Sh result` for closure bloat and `nix build --rebuild` once.
6. Run `/nix-review`.

Report: builder chosen and why, hash provenance, test status, closure size.
