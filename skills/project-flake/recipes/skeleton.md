# Skeleton: flake.nix, components, wiring

## flake.nix

Thin: inputs, systems, one `pkgs` per system, wiring of `nix/*.nix`.

```nix
{
  # Флейк проекта по контракту project-flake: компоненты (nix/components.nix),
  # пакет на компонент (nix/<компонент>.nix), образы dockerTools (nix/images.nix),
  # граф сервисов nixosModules.default (nix/module.nix), checks.vm (nix/vm-test.nix),
  # devShell (nix/devshell.nix). Кэши: nixpkgs-зависимости приходят бинарно
  # (rule-nix-heavy-build-limits).
  description = "<project>: <one line>";

  nixConfig = {
    extra-substituters = [ "https://cache.nixos.org" "https://nix-community.cachix.org" ];
    extra-trusted-public-keys = [
      "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
      "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
    ];
  };

  inputs = {
    # Пин nixpkgs принадлежит проекту (ветка; ревизию держит flake.lock).
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # Только если проект использует wk; wk следует пину проекта.
    wk.url = "github:BadRabbit00/wk/<rev>";
    wk.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, wk }:
    let
      inherit (nixpkgs) lib;
      systems = [ "x86_64-linux" "aarch64-linux" ];
      eachSystem = f: lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      linux = pkgs: lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux;
      project = "<project>"; # имя сервиса, пользователя, базы и префикс образов
      components = import ./nix/components.nix;
    in
    {
      lib = { inherit components; };

      packages = eachSystem (pkgs:
        let
          own = import ./nix/packages.nix { inherit pkgs; };
        in
        own
        // { default = own.orders; }
        // linux pkgs (import ./nix/images.nix { inherit pkgs project components; packages = own; }));

      nixosModules.default = import ./nix/module.nix { inherit self project components; };

      checks = eachSystem (pkgs:
        let
          own = import ./nix/packages.nix { inherit pkgs; };
        in
        own
        // linux pkgs { vm = import ./nix/vm-test.nix { inherit pkgs self project components; }; });

      devShells = eachSystem (pkgs: {
        default = import ./nix/devshell.nix {
          inherit pkgs;
          wk = wk.packages.${pkgs.stdenv.hostPlatform.system}.wk;
        };
      });

      formatter = eachSystem (pkgs: pkgs.nixfmt);
    };
}
```

Notes:

- CUDA or unfree: replace `nixpkgs.legacyPackages.${system}` with one
  `import nixpkgs { inherit system; config = { … }; }` (see `cuda.md`). Never
  import nixpkgs twice with different config for the same system.
- Projects without wk: drop the input and the `wk` argument.
- Systems: what really builds. Services are Linux only; a portable CLI adds
  `aarch64-darwin` (nixpkgs 26.11 dropped `x86_64-darwin`). Check with
  `nix flake check --no-build --all-systems`.
- `packages.default` is the main component. For a toolbox of several CLIs use
  `pkgs.symlinkJoin { name = "<project>"; paths = lib.attrValues own; }`.

## nix/components.nix

Pure data. No `pkgs`, no derivations, no paths into the store: tools read it
with `nix eval --json .#lib.components` without building anything.

```nix
# Компоненты проекта: единственный источник для images.nix, module.nix,
# vm-test.nix и для sec-vm. Имена переменных окружения — без значений.
{
  api = {
    kind = "service";
    package = "orders";        # attr in packages.<system>
    command = "orders-api";    # binary in that package; null = meta.mainProgram
    args = [ ];                # extra argv, never spaces inside `command`
    image = "image-api";
    port = 8000;
    health = "/health";
    needs = [ "postgres" "redis" ];
    after = [ "migrate" ];
    wire = {
      ORDERS_DATABASE_URL = "postgres:asyncpg";
      ORDERS_REDIS_CACHE_URL = "redis:0";
      ORDERS_HTTP_PORT = "port";
    };
    env = [ "ORDERS_DATABASE_URL" "ORDERS_REDIS_CACHE_URL" "ORDERS_HTTP_PORT" "ORDERS_SSO_JWT_SECRET" ];
    envExample = "src/orders/.env.example";
    gpu = false;
  };
  worker = {
    kind = "worker";
    package = "orders";
    command = "orders-worker";
    args = [ ];
    image = "image-api";       # several components may share one image
    port = null;
    health = null;
    needs = [ "postgres" "redis" ];
    after = [ "migrate" ];
    wire = { ORDERS_DATABASE_URL = "postgres:asyncpg"; ORDERS_REDIS_CACHE_URL = "redis:0"; };
    env = [ "ORDERS_DATABASE_URL" "ORDERS_REDIS_CACHE_URL" ];
    envExample = "src/orders/.env.example";
    gpu = false;
  };
  migrate = {
    kind = "job";
    package = "orders";
    command = "orders-migrate";
    args = [ ];
    image = "image-api";
    port = null;
    health = null;
    needs = [ "postgres" ];
    after = [ ];
    wire = { ORDERS_DATABASE_URL = "postgres:asyncpg"; };
    env = [ "ORDERS_DATABASE_URL" ];
    envExample = "src/orders/.env.example";
    gpu = false;
  };
}
```

Field rules:

- `kind`: `service` (listens on `port`), `worker` (no port, long-running),
  `job` (oneshot: migrations, seed), `frontend` (static files served on
  `port`), `cli`, `app` (desktop/mobile; no module entry).
- `needs` values the generic module sets up: `postgres`, `redis`, `rabbitmq`,
  `mqtt`. `s3` and `mongodb` are allowed but the project adds them to the module
  itself (an assertion fails until it does). Anything else is a component of its own or
  a third-party image (see `compose-migration.md`).
- `after`: names of `job` components that must finish first (migrations).
- `wire`: variable → rule the module turns into a value. Rules:
  `postgres[:driver]` (`postgresql[+driver]:///<project>?host=/run/postgresql`,
  peer auth), `redis[:db]`, `rabbitmq`, `mqtt`, `port` (the component's
  port), `literal:<value>`. This is how the project's own variable names
  (`ORDERS_DATABASE_URL`, not `DATABASE_URL`) and URL schemes reach the units.
- `env` lists every variable the component reads, wired or not. The rest come
  from the module's `environmentFile` (secrets) or `environment` (non-secret).
- `envExample`: the committed `.env.example` with placeholder values
  (`rule-secrets-env-example-reference`). `checks.vm` uses it as the fake env,
  minus wired variables; it must pass the service's own validation (URL
  fields as URLs, keys long enough). Never point it at a real `.env`.
- Every field is present in every entry (`null`/`[ ]`/`false` when unused), so
  consumers need no defaults.

## nix/packages.nix

```nix
{ pkgs }:
{
  orders = pkgs.callPackage ./orders.nix { };
  web = pkgs.callPackage ./web.nix { };
}
```

Each `nix/<component>.nix` follows the stack recipe. `meta.mainProgram` is set
on every runnable package so `lib.getExe` works.
