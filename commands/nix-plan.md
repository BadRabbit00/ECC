---
description: Plan a Nix change (flake, module, package, devShell, image) with the nix-architect agent — files, order, verification gate, risks. WAIT for confirmation before editing. Use for any non-trivial .nix work.
argument-hint: "[what to change]"
---

# /nix-plan

Invoke the **nix-architect** agent with `$ARGUMENTS` and the current repo. It reads `flake.nix`, the lock, entry modules and relevant files, then returns: goal restated, decision points (new file vs edit, overlay vs override, nixpkgs vs custom package, home.file vs activation merge), files table, verification gate (`git add` → `nix flake check --no-build` → `nixos-rebuild build` → `nvd diff` → Arch HM build → `nixos-rebuild test` → `switch`), risks (IFD, build cost from `nix build --dry-run`, hardware throttle, rollback).

Present the plan and stop. Do not write files until the user confirms. For a one-line change say so and skip the plan.
