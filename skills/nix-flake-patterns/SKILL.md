---
name: nix-flake-patterns
description: "How to structure and write flakes: inputs with follows, outputs per system, devShells with pinned toolchains, overlays vs overrideAttrs, nixosConfigurations and homeConfigurations with specialArgs, apps and checks, lock discipline. Use when creating a flake.nix, adding a devShell, wiring a new input, or reviewing why a flake evaluates slowly or impurely."
---

# Flake patterns

## Skeleton every project starts with

```nix
{
  description = "<one line>";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    # Every extra input follows nixpkgs so the closure has ONE nixpkgs.
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in {
        devShells.default = pkgs.mkShell {
          packages = [ pkgs.python3 pkgs.uv pkgs.ruff ];
          shellHook = ''
            export PROJECT_ROOT="$PWD"
            [ -f .env ] && set -a && . ./.env && set +a
          '';
        };
        packages.default = pkgs.callPackage ./package.nix { };
        checks.default = self.packages.${system}.default;
        formatter = pkgs.nixfmt-rfc-style;
      });
}
```

Without flake-utils: write `forAllSystems = nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-linux" ]` and index outputs by system yourself. Do not add flake-parts to a small project.

## Inputs

- `inputs.<x>.inputs.nixpkgs.follows = "nixpkgs"` on every input that has its own nixpkgs. Check with `nix flake metadata`: one nixpkgs node, not three.
- Pin to a branch, not a tag you never bump: `github:owner/repo/branch`. For reproducibility the lock file does the pinning; commit `flake.lock` always.
- Non-flake sources: `url = "github:o/r"; flake = false;` then use as a path.
- Update one input at a time (`nix flake update <input>`) and build before committing the lock.

## devShells

- `packages` for tools, `buildInputs` only when something must be linked against. `nativeBuildInputs` in shells is the same as `packages`.
- Language toolchains come from nixpkgs: `pkgs.rust-bin` (via rust-overlay) or `pkgs.cargo`/`pkgs.rustc`; `pkgs.python3.withPackages (ps: [...])` or uv2nix for lockfile fidelity; `pkgs.nodejs_22` + `pkgs.pnpm`; `pkgs.go`.
- `LD_LIBRARY_PATH` hacks are a smell; prefer `pkgs.lib.makeLibraryPath` only for Python wheels with native deps you cannot build.
- Secrets: read `.env` in `shellHook` or use direnv `dotenv_if_exists`; on this machine sops-decrypted files at `/run/secrets/<name>` can be exported in the hook.
- Several shells: `devShells.{default,ci,docs}`; CI runs `nix develop .#ci -c <cmd>`.

## Overlays vs overrides

- Fix one package for one consumer: `pkg.overrideAttrs (old: { … })` or `pkg.override { dep = other; }` inline.
- Fix it everywhere in a configuration: an overlay in `nixpkgs.overlays` (NixOS) or `pkgs = import nixpkgs { inherit system; overlays = [ … ]; }` (flake). Keep overlays in `overlays/<name>.nix`, one package per file.
- `final: prev:` naming. Use `prev.<pkg>` for the thing being changed, `final.<dep>` for dependencies.
- Python packages: `pkgs.python3.override { packageOverrides = pyfinal: pyprev: { … }; }`.

## NixOS and Home Manager outputs

```nix
nixosConfigurations.<host> = nixpkgs.lib.nixosSystem {
  system = "x86_64-linux";
  specialArgs = { inherit inputs; };
  modules = [
    ./hosts/<host>
    home-manager.nixosModules.home-manager
    {
      home-manager.useGlobalPkgs = true;
      home-manager.useUserPackages = true;
      home-manager.extraSpecialArgs = { inherit inputs; isNixOS = true; };
      home-manager.users.<user> = import ./home;
    }
  ];
};
homeConfigurations."<user>@<host>" = home-manager.lib.homeManagerConfiguration {
  pkgs = nixpkgs.legacyPackages.x86_64-linux;
  extraSpecialArgs = { inherit inputs; isNixOS = false; };
  modules = [ ./home ];
};
```

- Pass platform facts (`isNixOS`) through `specialArgs`/`extraSpecialArgs`, never detect them with `builtins.pathExists "/etc/NIXOS"`.
- This repo: `nixosConfigurations.badrabbitpc` and `homeConfigurations."badrabbit@ARCH-BOX"` share `home/`; every platform difference is guarded by `isNixOS`.

## checks, apps, packages

- `checks.<system>.<name>` are built by `nix flake check`; put lint (`statix`, `deadnix`), unit tests, and VM tests there (see `nix-testing`).
- `apps.<system>.<name> = { type = "app"; program = "${pkg}/bin/<exe>"; }` for `nix run .#<name>`.
- `packages.<system>.<name> = pkgs.callPackage ./nix/<name>.nix { }`: keep derivations in their own files, `callPackage` injects dependencies.

## Purity and speed

- `--impure` is needed only for `builtins.getEnv`, `<nixpkgs>` paths or reading files outside the flake. If a target needs it permanently, document why (this repo: `--impure` for the Arch HM target because of nixGL detection).
- Avoid IFD in flakes (`lib.importJSON "${drv}/…"`, `builtins.readFile` of an output). When unavoidable, isolate it in one derivation so the rest of the eval stays fast.
- Big `let` blocks that build strings with `${pkgs.x}` force those packages to be realised at eval time of the string? No, but they do force download when the string is used in a build. Keep eval cheap: no `builtins.fetchTarball` without a hash.
- `nix flake check --no-build` is the fast eval gate; run it before pushing.

## Project flakes

For an application repository (services, images, deployment) use the
`project-flake` skill: it fixes the house contract (`lib.components`, one
package per component, `nixosModules.default`, `checks.vm`) and its skeleton
uses `genAttrs` without flake-utils. This skill stays the general reference.
