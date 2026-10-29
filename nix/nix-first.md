# Nix-First Environment (always on)

This machine is NixOS. The system and the user environment are declarative
(`~/nixos-conf`, flakes + Home Manager). ECC's rules and skills were written for
machines where tools are installed ad hoc; on this machine they are adapted as
follows, and these rules override any ECC text that conflicts with them.

## Tooling

- Every project has its own `flake.nix` with a `devShell`. Build and run a
  project only through `nix develop -c <cmd>` (or direnv), `nix build`, `nix run`.
- One-off tools: `nix shell nixpkgs#<pkg> -c <cmd>`. Find packages with
  `nix search nixpkgs <name>` before anything else.
- Never rely on a bare `python`, `node`, `npx`, `uv`, `cargo`, `go`, `gcc` being
  on PATH, and never install into the system: no `pip install`, `pipx`,
  `npm install -g`, `cargo install`, `uv tool install`, `brew`, `apt`,
  `curl | sh`, `nix-env`. Declare the dependency in the flake instead.
- No inline interpreters (`python -c "…"`, `node -e "…"`, long `bash -c "…"`):
  write a script file (scratchpad or project) and run it through the devShell.
- Scripts that ship with ECC skills run only via the pinned `ecc-run` wrapper;
  ECC hooks run via `ecc-hook`. Both carry their own node/python/bash.

## Containers, secrets, builds

- Container images are built with `pkgs.dockerTools.buildLayeredImage` /
  `buildImage`, aiming at distroless contents. No `Dockerfile` with `apt-get`
  when a Nix expression can do it.
- Secrets and `.env` values enter the devShell via sops-nix / direnv; they are
  never hardcoded in `.nix` files and never committed.
- Heavy builds are throttled: `nix build --max-jobs 4 --cores 4`. Check
  `nix.settings.substituters` before building anything big from source.

## System changes

- To change the system, edit `.nix` files in `~/nixos-conf` and rebuild
  (`sudo nixos-rebuild switch --flake .#badrabbitpc`, or `home-manager switch`
  for the user layer). Never edit `/etc` by hand or use `nix-env`.
- New files must be `git add`ed before the Nix evaluator can see them.
