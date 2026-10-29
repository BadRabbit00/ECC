---
description: Update flake inputs safely — one input at a time or all, show what changed (nix flake metadata, nvd diff of the rebuilt system), rebuild without switching, and prepare a lock-only commit. Use for "update nixpkgs", "bump home-manager", "update the lock".
argument-hint: "[input name | all]"
---

# /nix-update

1. `nix flake metadata --json | jq '.locks.nodes | to_entries[] | {key, rev: .value.locked.rev}'` to record current revs.
2. `nix flake update <input>` for one input (or `nix flake update` for all; for nixpkgs prefer updating alone).
3. `git diff flake.lock` and summarise old → new rev per input.
4. `/nix-build system` (and the Arch HM target): see what recompiles vs downloads with `nix build --dry-run` first; abort and report if a monster would compile from source instead of the cache.
5. `nvd diff /run/current-system result`: list kernel, drivers (NVIDIA), desktop components, and anything removed.
6. Propose the commit `chore(flake): update <inputs>` with the rev table; commit only if asked. Remind that after a NVIDIA/kernel change the user should `nixos-rebuild boot` and reboot rather than `switch`.
