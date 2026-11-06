---
name: project-flake
description: "Write or extend a project's flake.nix to the house contract: one package per component, dockerTools images, a nixosModules.default that is the project's service graph (instead of docker-compose), machine-readable lib.components, checks with a NixOS VM test, devShell and formatter. Covers Python, Go, Node frontends, Rust/WASM, Android, CUDA/ML, static sites, infra-only repos and monorepos with microservices. Use when a project has no flake, has a devShell-only flake, runs its services through docker-compose/Dockerfiles, or when sec-vm/opencode/agy need the project in this shape."
---

# Project flake: the house contract

The goal is not "a flake that builds". The goal is a flake that every other
tool (sec-vm, opencode-sec, agy-sec, CI, the server) can read the same way,
whatever the stack: where the components are, how they start, what they need,
how to check they are alive. Stack-specific build recipes are in `recipes/`;
this file is the contract and the procedure.

## The contract

```
inputs.nixpkgs                      nixos-unstable; the project owns the pin
inputs.wk (if the project uses wk)  wk.inputs.nixpkgs.follows = "nixpkgs"

lib.components                      pure data, no pkgs (nix eval --json .#lib.components)
packages.<system>.<unit>            one per buildable unit (components.<c>.package points
                                    to it; API, worker and migrate may share one); tests in the build
packages.<system>.default           the main component (or a symlinkJoin of all)
packages.<system>.image-<component> Linux only, dockerTools, see recipes/images.md
nixosModules.default                the service graph: every runnable component,
                                    its DB/cache/broker, env file, ports
checks.<system>.<unit>              = the package (tests already in it)
checks.<system>.vm                  Linux only: runNixOSTest that imports the
                                    module and probes every health endpoint
devShells.<system>.default          everything for development, nothing installed
formatter.<system>                  pkgs.nixfmt
```

`lib.components` is the index everything else is generated from and checked
against:

```nix
lib.components = {
  api = {
    kind = "service";          # service | worker | frontend | cli | job | app
    package = "api";           # attr name in packages.<system>
    image = "image-api";       # attr name, or null
    port = 8000;               # null for workers, CLIs, apps
    health = "/health";        # HTTP path probed by checks.vm and sec-vm, or null
    command = "api";           # binary in the package; null = meta.mainProgram
    args = [ ];                # extra argv (never spaces inside command)
    needs = [ "postgres" "redis" ];   # postgres | redis | rabbitmq | s3 | mongodb | mqtt
    after = [ "migrate" ];     # job components that must finish first
    wire = {                   # variable -> value the module computes
      APP_DATABASE_URL = "postgres:asyncpg";
      APP_REDIS_URL = "redis:0";
      APP_PORT = "port";
    };
    env = [ "APP_DATABASE_URL" "APP_REDIS_URL" "APP_PORT" "APP_JWT_SECRET" ];  # NAMES only
    envExample = "src/api/.env.example";  # placeholders checks.vm uses as fake secrets
    gpu = false;               # true: needs CUDA at runtime (sec-vm has no GPU)
  };
  migrate = { kind = "job"; command = "api-migrate"; after = [ ]; … };
  worker = { kind = "worker"; command = "api-worker"; port = null; health = null; … };
};
```

Which outputs a project must have depends on what it is:

| Project | packages | images | nixosModules | checks.vm |
|---|---|---|---|---|
| Services, microservices, bots, APIs | yes | yes | yes | yes |
| Web frontend only | yes (static dist) | yes (caddy/nginx) | yes (static host) | yes |
| CLI, library, desktop, Android | yes | no | no | no (`lib.components` kind cli/app) |
| ML/CUDA service | yes | yes | yes | yes, with `gpu = true` components skipped or CPU |
| Infra/IaC, study, notebooks | devShell only | no | no | no (`lib.components = { }`) |

## File layout

Follows the wk rule `rule-deploy-build-files-placement`:

```
flake.nix                 thin: inputs, systems, wiring; no build logic
nix/components.nix        lib.components (data)
nix/<component>.nix       one package per component (callPackage-style)
nix/python-env.nix        shared dependency list (devShell + packages), if Python
nix/images.nix            all dockerTools images
nix/module.nix            nixosModules.default
nix/vm-test.nix           checks.vm
nix/devshell.nix          devShell
deploy/                   unit files, compose, scripts that deploy artifacts
src/<component>/          code (and its Dockerfile, if one exists); no .nix here
```

Skeleton and the module are in `recipes/skeleton.md` and `recipes/module.md`.

## Procedure

1. **Recon first** (`rule-deploy-recon-first`). Read: existing `flake.nix`/`nix/`,
   `shell.nix`, every `docker-compose*.yml`, `Dockerfile*`, `process-compose.yaml`,
   `deploy/`, systemd units, CI workflows, manifests (`pyproject.toml`,
   `requirements*.txt`, `uv.lock`, `go.mod`, `package.json` + lock, `Cargo.toml`,
   `build.gradle*`, `pubspec.yaml`), `.env.example`. Run
   `nix shell nixpkgs#gitleaks -c gitleaks dir . --redact` and stop to report if
   it finds live secrets in tracked files.
2. **List the components** from that recon: every compose service you own,
   every binary, every frontend, every worker/beat/cron. Third-party compose
   services (postgres, redis, rabbitmq, minio/seaweedfs, mongo, mqtt) become
   `needs`, not components. Write `nix/components.nix` first and show it to the
   user with the plan (which recipe per component, what changes in existing
   files) before writing build code.
3. **Packages**, one recipe per component from `recipes/`. Tests run in the
   build (`rule-deploy-nix-package`). Reuse what already builds; do not replace a
   working builder with your favourite one.
4. **Images** from the packages (`recipes/images.md`), only for components that
   run as services.
5. **Module** (`recipes/module.md`), generated from `lib.components`: one
   systemd unit per service/worker, `needs` mapped to NixOS services, one
   `environmentFile` option for secrets.
6. **checks.vm** (`recipes/vm-test.md`), also generated from `lib.components`.
7. **devShell** (`recipes/devshell.md`), formatter.
8. **Verify** (below). Only then report.

### Existing flakes: extend, do not rewrite

- Keep every output that CI, compose, scripts or README reference. If its name
  is off-contract, add the contract name as an alias
  (`image-backend = self.packages.${system}.backendImage;`), never rename.
- Never delete a Dockerfile, compose file or other build variant
  (`rule-deploy-no-variant-removal`). Compose stays as a variant; make it use
  the Nix images where it does not already, and keep both in sync in the same
  change (`rule-deploy-keep-variants-in-sync`).
- A project without Nix is migrated only when the user asked for it
  (`rule-nix-no-silent-migration`). Invoking this skill on it counts as asking.
- `flake.lock`: adding or changing inputs is part of this task; updating other
  inputs is not (`rule-nix-flake-lock-pinned`).
- Monorepo of independent sub-flakes (one flake per directory, own lock): apply
  the contract per sub-flake. Do not merge them into one root flake unless asked.
- Microservices in one repo with one dependency set: one env, many packages and
  images built from it (Jewelry/site `baseContainer`, hackaton-ic `nix/`).

## Rules

- Systems: `nixpkgs.lib.genAttrs` over the systems the project really supports;
  Linux-only outputs (images, module checks) under `lib.optionalAttrs
  pkgs.stdenv.hostPlatform.isLinux`. No flake-utils, no flake-parts.
- `pkgs = nixpkgs.legacyPackages.${system}` unless config is needed (CUDA,
  unfree): then one `import nixpkgs { inherit system; config = …; }` shared by
  all outputs. Unfree only with the user's consent (`rule-nix-unfree-consent`).
- Sources through `lib.fileset.toSource` or `lib.cleanSource` limited to the
  component's directory: an edit in the frontend must not rebuild the backend.
- Config only from environment and mounted files (`rule-deploy-config-from-env`):
  the same package and image run in the VM test, on stage and in prod.
- Secrets never enter the store: no `readFile` of a key, no token in `Env`,
  no `.env` in `src`. The module takes `environmentFile` as a **string** path
  (`types.str`), never `types.path`, and asserts it is not in the store. Fake
  values for checks.vm come only from committed `*.example` files (`envExample`).
- Every fetch has a hash. No `import <nixpkgs>`, no `builtins.getFlake`, no
  `--impure`, no IFD.
- Heavy builds with `--max-jobs 4 --cores 4`, CUDA only after checking that
  `cache.nixos-cuda.org` is a substituter (`rule-nix-heavy-build-limits`).
- What not to do and what to do instead: `anti-patterns.md`.

## Verify before saying "done"

```sh
nix flake check --no-build --all-systems                # evaluation of every listed system
nix fmt -- --check .                                    # formatter declared in the contract
nix eval --json .#lib.components                        # data parses, no derivations inside
nix build .#<component> --max-jobs 4 --cores 4 -L       # each component, tests included
nix build .#image-<component> && nix path-info -Sh ./result   # size sane, no gcc/python-dev
nix build .#checks.x86_64-linux.vm -L                   # whole graph boots, health answers
nix develop -c <main tool> --version                    # devShell works
```

`rule-deploy-verify-artifact`: every touched build variant is checked on the
built artifact. If the compose variant was touched and Docker is available,
`docker load < result` and run its smoke test too. Report what was verified
and what was not, with the command output.

## Recipes

- `recipes/skeleton.md`: flake.nix, components.nix, wiring
- `recipes/python.md`: nixpkgs deps, uv2nix, hash-pinned wheelhouse
- `recipes/go.md`, `recipes/node.md`, `recipes/rust.md`
- `recipes/android.md`: gradle mitmCache, Flutter
- `recipes/cuda.md`: CUDA/ML packages, devShell, images, `gpu = true`
- `recipes/images.md`: dockerTools images
- `recipes/module.md`: nixosModules.default from lib.components
- `recipes/vm-test.md`: checks.vm from lib.components
- `recipes/devshell.md`: devShell, .env, direnv
- `recipes/compose-migration.md`: docker-compose service by service
- `anti-patterns.md`
