# Rust (binaries, workspaces, WASM, maturin)

References: FlyBrain (`importCargoLock`, WASM, maturin), nix-agent
(`buildRustPackage`, `strictDeps`, cleanSourceWith), EvaProject (rust-overlay).

```nix
# nix/eva-api.nix — крейт eva-api из workspace.
{ lib, rustPlatform }:
let
  root = ../.;
in
rustPlatform.buildRustPackage {
  pname = "eva-api";
  version = "0.1.0";
  src = lib.fileset.toSource {
    inherit root;
    fileset = lib.fileset.unions [ (root + "/Cargo.toml") (root + "/Cargo.lock") (root + "/crates") ];
  };
  cargoLock.lockFile = ../Cargo.lock;   # без хеша; git-зависимости → outputHashes
  cargoBuildFlags = [ "-p" "eva-api" ];
  cargoTestFlags = [ "-p" "eva-api" ];
  strictDeps = true;
  meta.mainProgram = "eva-api";
}
```

- Workspace with several daemons: one `nix/<crate>.nix` per binary crate, all
  with the same `src` and `cargoLock`, differing in `-p`. Each is a component.
- Toolchain from `rust-toolchain.toml`: rust-overlay input
  (`inputs.nixpkgs.follows = "nixpkgs"`) and
  `rustPlatform = pkgs.makeRustPlatform { cargo = toolchain; rustc = toolchain; }`
  with `toolchain = pkgs.rust-bin.fromRustupToolchainFile ../rust-toolchain.toml`.
  Without such a file use nixpkgs' `rustPlatform`.
- Native deps: `nativeBuildInputs = [ pkg-config ]; buildInputs = [ openssl ];`.
- CUDA crates (candle, cudarc): `cuda.md`.
- WASM: `stdenv.mkDerivation` with `rustPlatform.cargoSetupHook`,
  `cargoDeps = rustPlatform.importCargoLock { lockFile = ...; }`, target
  `wasm32-unknown-unknown`, `lld` for the linker — copy FlyBrain's
  `packages.wasm` and its checkPhase.
- Python bindings: `python3Packages.buildPythonPackage` with
  `maturinBuildHook` and the same `cargoDeps` (FlyBrain `packages.engine`).
- A `systemd/*.service` file shipped in the repo is the hand-written variant of
  `nixosModules.default`: keep it in `deploy/`, mirror its options (User,
  hardening, env) in the module.
