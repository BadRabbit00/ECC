---
description: Reclaim disk safely — show generations and store size, delete old generations with a retention window, nix-collect-garbage, nix store optimise, verify. Asks before deleting anything.
argument-hint: "[retention like 14d]"
---

# /nix-gc

1. Report first: `df -h /nix`, `du -sh /nix/store` (or `nix path-info -Sh /run/current-system`), `sudo nix-env --list-generations -p /nix/var/nix/profiles/system`, `home-manager generations | head`, `nix-store --gc --print-dead | wc -l`.
2. Propose: keep the current and previous system generation at least; `sudo nix-collect-garbage --delete-older-than ${ARGUMENTS:-14d}`, then `nix store optimise`. Ask for confirmation; deleting generations removes boot entries.
3. After confirmation run them, then `df -h /nix` again and `nix store verify --all` only if corruption is suspected.

Never delete the running generation or GC roots under `.direnv/` without saying which projects lose their cached shells.
