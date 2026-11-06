---
name: deploy-variants
description: Use when building, packaging, or deploying a project - surveying existing build variants, choosing between Nix package, dockerTools image, Dockerfile + compose, NixOS module, Quadlet, or Nix-only local stack, keeping several variants in sync, CI publishing, rollout and rollback, and verification.
---

# Deploy variants

How a project is built and delivered (source: `09-deploy`). Writer rules: `deploy.md`, `compose.md`, `nix.md`. Secrets: `sops` skill and `secrets.md`.

## Contents

1. [Short version](#short-version) · 2. [Survey first](#survey-first) · 3. [Several variants](#several-variants) · 4. [Variants](#variants) · 5. [File layout](#file-layout) · 6. [Image and service properties](#image-and-service-properties) · 7. [CI, publishing, versions](#ci-publishing-versions) · 8. [Rollout and rollback](#rollout-and-rollback) · 9. [Verification](#verification) · 10. [Anti-patterns](#anti-patterns)

## Short version

1. Survey the repository before touching the build; reread the task; then act.
2. Variants: Nix package, distroless `dockerTools` image, Dockerfile + compose, NixOS module, podman + Quadlet, local stack without Docker.
3. The user asks for several variants → make each one complete and verified.
4. The repository has several → maintain **all** of them; one build/run change goes into every variant in one commit.
5. New project, nothing requested → Nix package + distroless `dockerTools` image.
6. CI builds the artifact once; deploys by digest; servers never build.
7. Secrets arrive at runtime; never in images, `/nix/store`, or the repository.
8. Every variant is verified: builds, starts, passes the main scenario (smoke test or VM test).

## Survey first

| Look at | Meaning |
|---|---|
| `flake.nix`: `packages`, `apps`, `checks`, `nixosModules`, `devShells` | Nix packages, `dockerTools` images, NixOS modules, VM tests |
| `nix/` (`<component>.nix`, `images.nix`, `module.nix`, `vm-test.nix`) | build and deploy expressions |
| `src/<component>/Dockerfile`, `.dockerignore` | classic image builds |
| `compose.yaml`, `docker-compose*.yml`, `compose.override.yaml` | compose runs; `docker-compose.prod.yml` for prod |
| `deploy/`: `*.container`, `*.network`, `*.volume`, systemd units, install scripts | Quadlet or systemd on servers |
| `.github/workflows/` | what CI builds, tests, publishes, on which events |
| `Makefile`, `justfile`, `README.md` | the commands people really use |

Then: the user named a variant → use it, even against the project's habit (say so). Not named → continue what exists; add nothing new unasked. New project → Nix package + `dockerTools` image. State the variants in the plan in one line: «Сборка: Nix-пакет + образ dockerTools + Dockerfile/compose — обновлю все три».

## Several variants

Requested → each complete: working, verified, with a run command in the README. A placeholder "for later" is not a variant.

Existing → keep all in sync in one commit:
- dependencies (Nix expression; Dockerfile manifest and lock file);
- language/runtime version (nixpkgs package and Dockerfile base image: same major.minor);
- env vars, ports, entry point, command, healthcheck;
- user, volumes, working dirs, read-only filesystem;
- migration step and start order;
- runtime system libraries and binaries.

Verify each touched variant; an unverified one is named in the report. A variant is never deleted without a direct request.

## Variants

| Variant | Result | When |
|---|---|---|
| Nix package | program in `/nix/store`, `nix run .#<component>` | local work, CLIs, Nix hosts; base for the image and the module |
| Distroless `dockerTools` image | OCI image with no shell or package manager | default for anything going to a server |
| Dockerfile + compose | classic image | on request; PaaS without Nix; contributors without Nix |
| NixOS module | systemd service on a NixOS host, no containers | own NixOS server |
| Podman + Quadlet | containers as systemd units | non-NixOS server; instead of compose in prod |
| Local stack without Docker | PostgreSQL, Redis, services from Nix in one command | development without Docker |

**Nix package.** `nix/<component>.nix` included by `flake.nix`: `buildPythonApplication` (`pyproject = true`), `buildGoModule` (`vendorHash`), `buildNpmPackage` (`npmDepsHash`); dependencies from the same nixpkgs as the devShell. Tests run at build (`pytestCheckHook`) and in `nix flake check`. Hashes updated with lock files in the same commit. Python dev runs may skip the package: `nix develop -c uvicorn app.main:app --reload`.

**`dockerTools` image.** From the package, with `buildLayeredImage` (archive) or `streamLayeredImage` (stream, saves store space). Only the closure plus runtime needs: `cacert`, `dockerTools.fakeNss`, `tzdata` if needed. One image per component (one image with several commands is fine for API + worker that must match).

```nix
packages.${system}.api-image = pkgs.dockerTools.buildLayeredImage {
  name = "ghcr.io/<org>/<project>-api";
  tag = self.shortRev or "dirty";
  contents = [ api pkgs.cacert pkgs.dockerTools.fakeNss ];
  extraCommands = "mkdir -m 1777 tmp";
  config = {
    Cmd = [ "${api}/bin/api" ];
    User = "65534:65534";
    ExposedPorts."8000/tcp" = { };
    Env = [ "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt" ];
    Labels."org.opencontainers.image.revision" = self.shortRev or "dirty";
  };
};
```

Load: `nix build .#api-image --out-link result-api-image && docker load -i result-api-image` (stream: `"$(nix build .#api-image --print-out-paths)" | docker load`). Whole system: `nix run .#images && docker compose up -d`; compose uses `image:` tags set by that app. Publish with `skopeo copy docker-archive:… docker://…`. Healthcheck is a subcommand of the program (`api healthcheck`), never `curl`.

**Dockerfile + compose.** Rules in `compose.md`: multi-stage, non-root, pinned bases, `.dockerignore` per context, `127.0.0.1` ports, named volumes, healthchecks. Dockerfile in `src/<component>/`, build context = that folder; compose in the root. With Nix in the project, base image and runtime versions match `flake.lock`.

**NixOS module.** `nixosModules.<component>` with `services.<component>.*` options and a systemd unit from the package: `DynamicUser` or a dedicated user, `StateDirectory`, `ProtectSystem = "strict"`, `NoNewPrivileges`, `Restart = "on-failure"`; secrets via `EnvironmentFile`/`LoadCredential` from outside the store (sops-nix when sops is on). Deploy with `nixos-rebuild switch --flake .#<host> --target-host <host>` (or deploy-rs/colmena if already used) — by the user; rollback = previous generation. Verified with `pkgs.testers.runNixOSTest`.

**Podman + Quadlet.** `deploy/*.container|network|volume` installed into `/etc/containers/systemd/`; image by digest; limits in the unit:

```ini
[Container]
Image=ghcr.io/<org>/<project>-api@sha256:<digest>
EnvironmentFile=/etc/<project>/api.env
PublishPort=127.0.0.1:8000:8000
Volume=<project>-data:/var/lib/<project>
ReadOnly=true
User=10001
HealthCmd=/bin/api healthcheck
```

A server already on compose stays on compose; moving to Quadlet is a separate agreed task.

**Local stack without Docker.** process-compose via services-flake (`nix run .#dev`), data in `.dev/`. A new flake dependency: only with agreement or if already used. Never prod.

## File layout

`flake.nix`, `flake.lock`, `compose.yaml`, `.env.example` in the root. All Nix expressions in `nix/` (no `.nix` in `src/`). Dockerfile and `.dockerignore` in `src/<component>/`. Quadlet/systemd units and install/backup scripts in `deploy/`. Build and deploy code never goes into `src/` (except the Dockerfile's context). A service moved to its own repository takes its `nix/` recipe along.

## Image and service properties

Non-root (numeric `User`, `DynamicUser`) · read-only root filesystem; writes to volumes, `StateDirectory`, `/tmp` · a healthcheck that checks readiness · graceful SIGTERM (finish requests, close connections) · labels `org.opencontainers.image.revision|version|source` · no secrets in `ENV`/`ARG`/layers/Nix · configuration only from env and mounted files: one artifact for test and prod.

## CI, publishing, versions

- PR: linters, types, tests, `nix flake check`, every existing variant built, image smoke test. Publishing is a separate workflow with write rights; the checking one is read-only.
- Build once; servers pull images or Nix closures, never `git pull` and build.
- Registry GHCR; tags `sha-<short>`, `main`, `vX.Y.Z` (semver tag on a commit already in `main` with full CI; matches the version in code). Provenance attestation on publish.
- Deploy by digest. Nix store cache and binary caches in CI; heavy builds with limited parallelism (`nix.md` R-NIX-HEAVY-BUILDS).

## Rollout and rollback

- Production only with the user's permission for one concrete action.
- Order: backup → migrations as their own step → version switch → health check → main scenario; failure → rollback.
- The rollback is known and tested beforehand: previous digest, previous NixOS generation, previous tag. Migrations are expand-then-contract so the previous code runs on the new schema during a rollback.
- Before switching, workers stop gracefully: unfinished jobs save state or return to the queue.

## Verification

| Variant | Check |
|---|---|
| Nix package | `nix build .#<component>` with its tests; `nix flake check` green |
| any image | smoke test as on the server: non-root, read-only root, no capabilities, data only in the volume; starts, healthcheck green, main scenario passes |
| Dockerfile + compose | `docker compose config --quiet`; `docker compose up -d --build` with `.env` from `.env.example` brings everything up |
| NixOS module, server units | VM test: install, start via the unit, main scenario, restart, stop |

Tests that bypass the real way of running do not prove the deployment; packaging-dependent behaviour (subprocesses, paths, permissions, env) is checked on the built artifact.

## Anti-patterns

| Anti-pattern | Instead |
|---|---|
| writing a Dockerfile without noticing the flake already builds an image | survey, continue the accepted variant |
| updating a dependency in one variant only | every variant, one commit |
| deleting the "extra" Dockerfile because Nix exists | only on request |
| a TODO variant "for later" | complete and verified, or not at all |
| building on the server from `git pull` | CI builds, deploy by digest |
| deploying `latest` or `main` tags | digest or semver |
| secrets in Dockerfile `ENV`, image `config.Env`, or `.nix` | runtime env file, `LoadCredential`, sops |
| `curl` healthcheck in a distroless image | the program's own healthcheck subcommand |
| "tests are green, so the image works" | smoke test of the image, VM test of the deployment |
| migrations at the start of every replica | a separate migration step before the switch |
