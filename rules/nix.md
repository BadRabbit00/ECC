---
paths:
  - "**/*.nix"
  - "flake.lock"
---

# Nix files

## Scope

`flake.nix`, `nix/*.nix`, NixOS / Home Manager modules. Host-install bans are enforced by hooks. Deep Nix work goes to the Nix agents (`nix-architect`, `nix-engineer`, `nix-reviewer`) and the `nix-*` skills.

## Rules

- R-NIX-LAYOUT: `flake.nix` and `flake.lock` sit in the repo root; every other Nix expression lives in `nix/` (`<component>.nix`, `images.nix`, `module.nix`, `vm-test.nix`). There are no `.nix` files in `src/`.
- R-NIX-DEVSHELL: `devShells.default` contains everything needed to work: language and libraries, linters, DB clients. Use one devShell per component when they differ (`nix develop .#api`). `shellHook` only exports variables and creates `.dev/`; it never installs or downloads.
- R-NIX-PYTHON: Python dependencies come from `python3XX.withPackages`. A package missing from nixpkgs is described in `nix/` (`buildPythonPackage` with a pinned version and hash). No `.venv`, no `pip`.
- R-NIX-LOCK: never touch `flake.lock` outside a task that is about updating inputs. Update one input at a time, then build and test.
- R-NIX-NO-SECRETS: no secret in any `.nix` file; it would end up in `/nix/store`.
- R-NIX-HEAVY-BUILDS: heavy builds run with limits (`--max-jobs 4 --cores 8` or less) and only after checking that the binary cache has the package.
- R-NIX-IMAGES: images are built with `dockerTools.buildLayeredImage` / `streamLayeredImage` from the package: `cacert`, `fakeNss`, non-root `User`, OCI revision label, and no shell.

## Examples

### R-NIX-DEVSHELL — no side effects in shellHook

Bad:
```nix
devShells.default = pkgs.mkShell {
  packages = [ pkgs.python312 ];
  shellHook = ''
    python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
  '';
};
```
Why: a second dependency source next to `flake.lock`, network access on every entry, nothing reproducible.

Good:
```nix
devShells.default = pkgs.mkShell {
  packages = [
    (pkgs.python312.withPackages (ps: [ ps.fastapi ps.uvicorn ps.sqlalchemy ps.alembic ps.pytest ps.httpx ]))
    pkgs.ruff pkgs.postgresql
  ];
  shellHook = ''export PYTHONPATH="$PWD/src/api''${PYTHONPATH:+:$PYTHONPATH}"'';
};
```

### R-NIX-IMAGES — distroless image from the package

Bad:
```nix
api-image = pkgs.dockerTools.buildImage {
  name = "api"; tag = "latest";
  copyToRoot = [ pkgs.bashInteractive pkgs.coreutils api ];
  config.Cmd = [ "bash" "-c" "api" ];
};
```
Why: shell and coreutils in production, the `latest` tag, root user, and SIGTERM goes to bash.

Good:
```nix
api-image = pkgs.dockerTools.buildLayeredImage {
  name = "ghcr.io/<org>/<project>-api";
  tag = self.shortRev or "dirty";
  contents = [ api pkgs.cacert pkgs.dockerTools.fakeNss ];
  config = {
    Cmd = [ "${api}/bin/api" ];
    User = "65534:65534";
    Labels."org.opencontainers.image.revision" = self.shortRev or "dirty";
  };
};
```
