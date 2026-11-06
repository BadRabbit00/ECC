---
description: Build a flake output, the NixOS system or the Home Manager generation the safe way — dry-run first, throttled, logs streamed, then nvd diff. Never switches. Use whenever something must be built or the user asks "does it build".
argument-hint: "[.#attr | system | home | arch]"
---

# /nix-build

Pick the target from `$ARGUMENTS` (default: `system` in `~/nixos-conf`, `.#default` elsewhere):

- `system`: `nixos-rebuild build --flake .#badrabbitpc` then `nvd diff /run/current-system result`.
- `home`: `nix build --impure --no-link --print-out-paths --expr '(builtins.getFlake (toString ./.)).nixosConfigurations.badrabbitpc.config.home-manager.users.BadRabbit.home.activationPackage'`.
- `arch`: `nix build --impure --no-link '.#homeConfigurations."badrabbit@ARCH-BOX".activationPackage'`.
- `.#attr`: `nix build .#attr -L --no-link --print-out-paths`.

Always: `git add` new files first; `nix build --dry-run` to see what compiles vs downloads and check `nix show-config | grep substituters` when a monster (chromium, LLVM, CUDA, llama-cpp) would compile; `--max-jobs 4 --cores 4` (CUDA: `--max-jobs 2 --cores 8`); `-L` for logs, `nom` if available for the graph.

On failure hand off to **nix-build-resolver**. Report commands, exit codes, `nvd diff` summary, and what was fetched vs built. The user runs `nixos-rebuild test/switch` themselves.
