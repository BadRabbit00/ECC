# docker-compose → the contract, service by service

Compose stays as a build variant (`rule-deploy-no-variant-removal`); the goal
is that everything compose knows also lives in the flake, and that compose
runs the Nix images.

## Mapping table

| compose | contract |
|---|---|
| service with `build:` (your code) | component: `packages.<c>`, `image-<c>`, entry in `lib.components` |
| `command:` / `entrypoint:` | `command` = the binary name only, the rest goes to `args` (`command: celery -A app worker` → `command = "celery"; args = [ "-A" "app" "worker" ];`) |
| several services from one build (api, worker, beat) | several components, same `package`, different `command`, same `image` |
| `ports: "8000:8000"` | `port = 8000` |
| `healthcheck: curl …/health` | `health = "/health"` |
| `depends_on: db, redis` | `needs = [ "postgres" "redis" ]` |
| `postgres:16`, `timescale/timescaledb` | `needs = [ "postgres" ]`; TimescaleDB (TSL licence: ask): `extensions = ps: [ ps.timescaledb ];` plus `settings.shared_preload_libraries = [ "timescaledb" ];`, and `CREATE EXTENSION` as superuser in `systemd.services.postgresql-setup.postStart` (the owner role used by migrations may not be allowed to) |
| `pgvector/pgvector` | `services.postgresql.extensions = ps: [ ps.pgvector ];` |
| `redis` | `needs = [ "redis" ]` |
| `rabbitmq` | `needs = [ "rabbitmq" ]` |
| `minio`, `seaweedfs`, `garage` | `needs = [ "s3" ]` (`module.md`) |
| `mongo` | `needs = [ "mongodb" ]` (unfree, ask) |
| `emqx`, `mosquitto` | `needs = [ "mqtt" ]` (mosquitto) |
| `nginx`/`traefik`/`caddy` in front | the module's Caddy/nginx virtual host; copy its routes |
| `migrate` one-shot service | `kind = "job"` component |
| `environment:` with literal values | non-secret: module `environment`; secret: names in `env`, values in `environmentFile` |
| `env_file: .env` | `environmentFile` |
| `secrets:` (docker secrets) | a file path option, or a key in `environmentFile` |
| `volumes:` named volume | `StateDirectory` of the unit (module creates it) |
| `ngrok`, `cloudflared`, tunnels | not part of the project graph; leave in compose, mention it |
| vendor image with no NixOS module and no source | third-party image (below) |

## Third-party images

Pinned by digest and hash, fetched at build time on the host (the VM still has
no network):

```nix
mediamtx = pkgs.dockerTools.pullImage {
  imageName = "bluenviron/mediamtx";
  imageDigest = "sha256:…";           # docker buildx imagetools inspect <image>:<tag>
  hash = "sha256-…";                  # nix-prefetch-docker / fakeHash
  finalImageTag = "1.9.3";
};
```

In the module:

```nix
virtualisation.oci-containers = {   # backend (docker/podman) выбирает хост, не проект
  containers.mediamtx = {
    image = "bluenviron/mediamtx:1.9.3";
    imageFile = mediamtx;             # загружается из store, без registry
    ports = [ "127.0.0.1:8554:8554" ];
  };
};
```

Prefer a nixpkgs package or NixOS module when one exists (`services.mediamtx`
does); a pulled image is the fallback.

## Making compose use the Nix images

- Image names in compose match `image-<c>`: `image: <project>-api:<tag>`.
  Because the tag is the content hash, generate the override file instead of
  editing tags by hand: a `writeShellApplication` `load-images` that runs
  `docker load` for every `image-*` and writes `deploy/compose.nix.yml` with the
  loaded tags (KRAFTA `deploy/compose.nix.yml` is the pattern).
- Pinned third-party images in compose: `postgres:16-alpine@sha256:…`, never
  `:latest` (`rule-stack-versions-pinned`).
- Dockerfiles stay where they are (`src/<c>/Dockerfile`). If one installs with
  `apt-get`, say so in the report and offer the Nix image as the replacement;
  do not delete it.

## Order of work for a compose project

1. Table of compose services → components/needs (show it to the user).
2. Packages for your services, one at a time, each building with tests.
3. `lib.components`, images, module.
4. `checks.vm` green.
5. compose override using the Nix images; run it once if Docker is there.
