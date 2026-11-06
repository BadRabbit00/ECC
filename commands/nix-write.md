---
description: Implement an approved Nix plan with the nix-engineer agent — flake outputs, NixOS/HM modules, overlays, wrappers — then run the build gate. Use after /nix-plan or for small well-defined .nix edits.
argument-hint: "[plan or change description]"
---

# /nix-write

Hand `$ARGUMENTS` (and the approved plan if one exists) to the **nix-engineer** agent. It edits only the planned files, follows `nix-flake-patterns` / `nixos-module-patterns`, `git add`s new files, and runs `nix flake check --no-build` plus the build of the touched output (`nixos-rebuild build --flake .#badrabbitpc` or the HM activationPackage), throttled `--max-jobs 4 --cores 4`, then `nvd diff` when a system was built.

Then run `/nix-review` on the diff. Never switch the system from this command.
