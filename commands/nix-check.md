---
description: Lint and format Nix code — statix, deadnix, nixfmt (RFC style), nix flake check --no-build — and apply safe fixes. Use before committing .nix changes or when a reviewer asks for lint.
argument-hint: "[paths]"
---

# /nix-check

Run on `$ARGUMENTS` or the changed `.nix` files (`git diff --name-only -- '*.nix'`):

```bash
nix shell nixpkgs#statix nixpkgs#deadnix nixpkgs#nixfmt-rfc-style -c sh -c '
  statix check <paths> && deadnix --fail <paths> && nixfmt --check <paths>'
nix flake check --no-build
```

If the tools are already in PATH (this machine's `home.packages`), call them directly. Fix: `statix fix`, `deadnix -e`, `nixfmt <paths>`; show the diff of what the fixers changed. Report remaining warnings with file:line.
