# devShell

Everything for development, nothing installed (`rule-nix-flake-devshell`,
`rule-nix-shellhook-no-install`). Reference: dronessuperpuper `nix/devshell.nix`.

```nix
# nix/devshell.nix — язык, зависимости, линтеры, клиенты и серверы БД для тестов.
{ pkgs, wk ? null }:
let
  env = import ./python-env.nix { inherit pkgs; };
  python = env.python.withPackages (ps: env.runtimeDeps ps ++ env.testDeps ps);
in
pkgs.mkShell {
  packages = [ python pkgs.ruff pkgs.postgresql_16 pkgs.redis pkgs.jq pkgs.git ]
    ++ pkgs.lib.optional (wk != null) wk;

  # Только переменные и локальные каталоги.
  shellHook = ''
    export PYTHONPATH="$PWD/src/orders''${PYTHONPATH:+:$PYTHONPATH}"
    if [ -f .env ]; then
      set -a
      . ./.env
      set +a
    fi
  '';
}
```

- Same dependency list as the packages (`python-env.nix`), so what passes in
  the shell passes in the build.
- `.env` is sourced with `set -a … set +a` and a file check. Not
  `export $(cat .env | xargs)` (breaks on spaces and quotes; PsySite), and
  never `set -a` twice without `set +a` (SiteParser).
- sops: `sops exec-env secrets.sops.yaml '<cmd>'` as an alias or a
  `writeShellApplication` in `packages`; do not decrypt into variables in
  every `shellHook` (GeminiCLI falls back to a fake string silently).
- direnv: `.envrc` with `use flake` and `dotenv_if_exists .env`.
- Helper commands are `writeShellApplication` packages in the shell
  (nekta-setup `nk-*`, unic/db `db-up`), not aliases and not functions in
  `shellHook`.
- Local Postgres/Redis for development: the project's compose, or a
  `writeShellApplication` that starts a throwaway instance in `$PWD/.dev`
  (`rule-nix-dev-infrastructure`). Pick what the project already does.
- Several shells only for real differences: `default`, `ci` (no GUI/CUDA),
  `models`, `emulator`. `devShell` (singular) is deprecated: rename to
  `devShells.<system>.default`.
