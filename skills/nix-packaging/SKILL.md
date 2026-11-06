---
name: nix-packaging
description: "Packaging software with Nix: stdenv.mkDerivation phases, fetchers and SRI hashes (fake-hash trick, nurl, nix flake prefetch), language builders (buildNpmPackage/importNpmLock, buildPythonPackage/uv2nix, rustPlatform, buildGoModule), overrideAttrs and patches, substituteInPlace, wrappers (writeShellApplication, makeWrapper), checkPhase, meta, and distroless images with dockerTools. Use when packaging a tool, wrapping a script, fixing a hash, or building a container image."
---

# Packaging with Nix

## Derivation skeleton

```nix
{ lib, stdenv, fetchFromGitHub, cmake, pkg-config, openssl }:
stdenv.mkDerivation (finalAttrs: {
  pname = "thing";
  version = "1.2.3";
  src = fetchFromGitHub {
    owner = "o"; repo = "r";
    tag = "v${finalAttrs.version}";          # or rev = "<commit>"
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";   # fake first, see below
  };
  nativeBuildInputs = [ cmake pkg-config ];  # build-time tools
  buildInputs = [ openssl ];                 # linked libraries
  doCheck = true;
  meta = {
    description = "…";
    homepage = "https://…";
    license = lib.licenses.mit;
    mainProgram = "thing";                   # enables lib.getExe
    platforms = lib.platforms.linux;
  };
})
```

Phases: `unpack → patch → configure → build → check → install → fixup`. Override with `<phase>Phase = '' runHook pre<Phase>; …; runHook post<Phase> ''` and always keep the `runHook` pair. `dontBuild`, `dontConfigure`, `dontUnpack` for data-only packages. Use `stdenvNoCC` when nothing is compiled.

## Hashes

1. Put a fake hash (`lib.fakeHash` or all-A SRI), build, copy the `got:` hash from the error.
2. Or compute first: `nix flake prefetch github:o/r/<rev> --json | jq -r .hash` (matches `fetchFromGitHub`), `nix-prefetch-url --unpack <tarball>` + `nix hash to-sri sha256:<hex>`, `nurl <url> <rev>` prints the whole fetcher expression.
3. `fetchurl` hashes the file, `fetchzip`/`fetchFromGitHub` hash the unpacked tree: do not mix them.
4. Hash mismatch after a version bump = you forgot to update the hash, or upstream moved the tag (prefer `rev`).

## Patching sources

- `patches = [ ./fix.patch (fetchpatch { url = "…/commit/<sha>.patch"; hash = "…"; }) ];`
- `postPatch = '' substituteInPlace src/x.py --replace-fail '/usr/bin/foo' '${lib.getExe foo}' '';` (`--replace-fail` errors when the string is missing: always prefer it over `--replace-quiet`).
- Shebangs: `patchShebangs --build <dir>` in `postPatch`/`installPhase` rewrites `#!/usr/bin/env node` to store paths.
- `overrideAttrs (old: { patches = (old.patches or []) ++ [ ./x.patch ]; })` for one-off fixes to nixpkgs packages; `override { dep = other; }` to swap inputs.

## Language builders

| Ecosystem | Builder | Notes |
|---|---|---|
| Node (npm lock) | `pkgs.buildNpmPackage { npmDepsHash = "…"; }` or `pkgs.importNpmLock.buildNodeModules { npmRoot = src; nodejs; }` | importNpmLock needs no hash but reads the lock at eval (IFD-like); strip `devDependencies`/`overrides` when npm complains (see `home/ai/ecc`) |
| Node (pnpm) | `pnpm.fetchDeps { hash }` + `pnpmConfigHook` | |
| Python app | `python3.pkgs.buildPythonApplication { pyproject = true; build-system = [ hatchling ]; dependencies = [ … ]; }` | tests via `nativeCheckInputs = [ pytestCheckHook ]` |
| Python with lockfile | uv2nix / pyproject.nix (`workspace.loadWorkspace`, `mkPyprojectOverlay`) | exact wheels from `uv.lock`; this repo uses it in `home/ai/mcp/colab-mcp.nix` |
| Python env for scripts | `python3.withPackages (ps: [ ps.requests ])` | for wrappers and devShells |
| Rust | `rustPlatform.buildRustPackage { cargoHash = "…"; }` or `cargoLock.lockFile = ./Cargo.lock` | `useFetchCargoVendor = true` on new nixpkgs |
| Go | `buildGoModule { vendorHash = "…"; }` | `vendorHash = null` when vendored |
| Haskell, OCaml, Zig… | `haskellPackages.mkDerivation`, `buildDunePackage`, `zig.hook` | |
| CUDA | `cudaPackages.*`, `config.cudaSupport = true`, substituter `cache.nixos-cuda.org` | throttle: `--max-jobs 2 --cores 8` |

## Wrappers and scripts

```nix
pkgs.writeShellApplication {
  name = "tool-run";
  runtimeInputs = [ pkgs.python3 pkgs.jq ];      # prepended to PATH; shellcheck runs on build
  text = ''exec python3 ${src}/script.py "$@"'';
}
```

- `writeShellApplication` over `writeShellScriptBin`: `set -euo pipefail` and shellcheck for free.
- `makeWrapper` / `wrapProgram $out/bin/x --prefix PATH : ${lib.makeBinPath [ a b ]} --set VAR value` in `postFixup` for binaries that need env.
- `symlinkJoin { name; paths = [ … ]; }` to compose several packages into one output.
- Restrict what a wrapper may execute (as `ecc-run` does): `case "$script" in ${root}/*) …;; *) exit 64;; esac`.

## checkPhase and reproducibility

- Run upstream tests in `checkPhase` with the same interpreter the wrapper uses. Skip only network/HOME-dependent suites and say which in a comment.
- No network in builds except fixed-output fetchers. `HOME` is `/homeless-shelter`: set `HOME=$TMPDIR` in checks that need it.
- `nix build --rebuild` twice to check reproducibility; `diffoscope` for the difference.

## Container images (distroless, no Dockerfile)

```nix
pkgs.dockerTools.buildLayeredImage {
  name = "myapp";
  tag = "latest";
  contents = [ myapp pkgs.cacert pkgs.tzdata ];   # no bash, no coreutils unless needed
  config = {
    Cmd = [ "${lib.getExe myapp}" ];
    Env = [ "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt" ];
    ExposedPorts = { "8080/tcp" = { }; };
    User = "1000:1000";
  };
  extraCommands = "mkdir -p tmp && chmod 1777 tmp";
}
```

- `nix build .#image && docker load < result` (or `podman load`); `streamLayeredImage` pipes without a tarball in the store: `$(nix build --print-out-paths .#image) | docker load`.
- `fakeRootCommands` + `enableFakechroot = true` when files need an owner other than root.
- Non-root user, `cacert` for TLS, `tzdata` for zones, nothing else. Inspect size with `nix path-info -Sh .#image`.
- Compose/dev: run the Nix image like any other; do not write a `Dockerfile` that `apt-get`s a toolchain you already have in the devShell.

## Pitfalls

- `$out` must exist before copying into it: `mkdir -p $out/bin`.
- References to `/build` in the output fail the fixup check: do not bake `$TMPDIR` paths.
- Runtime deps are detected by scanning for store paths; a program that `exec`s `git` by name needs `wrapProgram --prefix PATH` or `runtimeInputs`.
- Large sources (models, datasets) never go into the store; keep them in `~/.eva/models`-style dirs and pass paths at runtime.
