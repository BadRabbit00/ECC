---
description: Answer dependency and size questions about a closure — why is X in the system, what is big, what changed between generations, who keeps a path from GC — with nix why-depends, nix-tree, nix path-info, nvd, nix-store --query.
argument-hint: "<question or store path/attr>"
---

# /nix-why

Map the question to the tool (`nix-toolkit` skill, "Evaluate and inspect"):

- "why is X in the closure": `nix why-depends <root> nixpkgs#X` (`--all`, `--derivation` for build-time); root = `/run/current-system`, `result`, or `.#attr`.
- "what is big": `nix path-info -Sh <root>`, `nix path-info -rSh <root> | sort -hk2 | tail -20`, `nix-tree <root>`.
- "what changed": `nvd diff <old> <new>` (generations under `/nix/var/nix/profiles/`), `nix-diff drvA drvB` for build inputs.
- "who keeps this alive": `nix-store --query --roots <path>`, `--referrers`.
- "which package provides <bin>": `nix-locate bin/<name>` or `nix search nixpkgs <name>`.

Run the command, quote the relevant lines, and state the answer in one sentence plus the fix if the dependency is unwanted (`override`, drop the option, `nix-collect-garbage`).
