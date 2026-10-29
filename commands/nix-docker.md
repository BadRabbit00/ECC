---
description: Build a distroless container image with pkgs.dockerTools (buildLayeredImage / streamLayeredImage) instead of a Dockerfile — contents, Cmd/Env/User/ExposedPorts, cacert and tzdata, non-root, size check, load into docker/podman.
argument-hint: "<package or flake output> [image name]"
---

# /nix-docker

1. Identify the runnable package (`packages.<system>.<name>` or `lib.getExe pkg`). If the app is not packaged yet, run `/nix-package` first.
2. Add `packages.<system>.image = pkgs.dockerTools.buildLayeredImage { … }` per the `nix-packaging` skill: `contents = [ app cacert tzdata ]`, `config.Cmd`, `Env` with `SSL_CERT_FILE`, `User = "1000:1000"`, `ExposedPorts`, writable `tmp` via `extraCommands`. No shell, no coreutils unless the app needs them. `streamLayeredImage` when the tarball should not land in the store.
3. Build and inspect: `nix build .#image --max-jobs 4 --cores 4`, `nix path-info -Sh result`, `nix-tree result` if large.
4. Load and smoke-test: `docker load < result` (or `$(nix build --print-out-paths .#image) | docker load`), `docker run --rm -p … <name>:<tag>` and hit the health endpoint.
5. If a `Dockerfile` with `apt-get`/`pip install` exists, propose replacing it and note anything the Nix image cannot do yet.

Report image name, size, Cmd, user, and the smoke-test output.
