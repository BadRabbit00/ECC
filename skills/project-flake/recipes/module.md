# nixosModules.default: the service graph

The module replaces docker-compose as the description of how the project runs:
one systemd unit per `service`/`worker`/`job` component, its `needs` as NixOS
services, secrets from one env file. It is generated from `lib.components`, so
adding a component is one entry in `nix/components.nix`.

Units run the Nix **packages** directly (not the images): no container runtime
in the VM test or on a NixOS server. Images remain for compose and registries.

## nix/module.nix

`project` (service, user, database and image prefix) is one value passed
from `flake.nix`, the same one `images.nix` and `vm-test.nix` get.

Replace `<project>` with the project name (lowercase, `[a-z0-9-]`).

```nix
# Граф сервисов проекта (вариант выкладки рядом с compose): юнит на каждый
# компонент из nix/components.nix, зависимости — штатные сервисы NixOS,
# секреты — из environmentFile. Тот же модуль поднимают checks.vm и sec-vm.
{ self, project, components }:
{ config, lib, pkgs, ... }:

let
  name = project;
  cfg = config.services.${name};
  own = self.packages.${pkgs.stdenv.hostPlatform.system};

  managedKinds = [ "service" "worker" "job" "frontend" ];
  managed = lib.filterAttrs (_: c: lib.elem c.kind managedKinds) components;
  enabledAll = lib.filterAttrs (n: _: cfg.components.${n}.enable) managed;
  units = lib.filterAttrs (_: c: c.kind != "frontend") enabledAll;
  needs = lib.unique (lib.concatMap (c: c.needs) (lib.attrValues enabledAll));
  has = n: lib.elem n needs;

  # Зависимости, которые модуль поднимает сам. Остальные (s3, mongodb) проект
  # добавляет в этот модуль явно — иначе assertion ниже.
  handled = [ "postgres" "redis" "rabbitmq" "mqtt" ];
  redisSocket = "/run/redis-${name}/redis.sock";

  exe = c: lib.getExe' own.${c.package}
    (if c.command != null then c.command else own.${c.package}.meta.mainProgram);

  # Зависимость → юнит, после которого стартует компонент.
  unitOf = {
    postgres = "postgresql.target"; # включает postgresql-setup (ensure*)
    redis = "redis-${name}.service";
    rabbitmq = "rabbitmq.service";
    mqtt = "mosquitto.service";
  };
  depsOf = c:
    lib.concatMap (n: lib.optional (unitOf ? ${n}) unitOf.${n}) c.needs
    ++ map (a: "${name}-${a}.service") (lib.filter (a: units ? ${a}) c.after);

  # Значение переменной по правилу из components.wire.
  wireValue = c: rule:
    let
      parts = lib.splitString ":" rule;
      kind = lib.head parts;
      arg = lib.concatStringsSep ":" (lib.tail parts);
    in
    if kind == "postgres" then
      "postgresql${lib.optionalString (arg != "") "+${arg}"}:///${name}?host=/run/postgresql"
    else if kind == "redis" then "unix://${redisSocket}?db=${if arg == "" then "0" else arg}"
    else if kind == "rabbitmq" then "amqp://guest:guest@127.0.0.1:5672/"
    else if kind == "mqtt" then "mqtt://127.0.0.1:1883"
    else if kind == "port" then toString c.port
    else if kind == "literal" then arg
    else throw "components.wire: неизвестное правило «${rule}»";
in
{
  options.services.${name} = {
    enable = lib.mkEnableOption name;

    environmentFile = lib.mkOption {
      # Строка, а не path: /run/secrets/... не должен копироваться в store.
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "/run/secrets/${name}.env";
      description = "KEY=VALUE file with secrets (sops-nix, agenix, or written by the operator).";
    };

    environment = lib.mkOption {
      type = lib.types.attrsOf lib.types.str;
      default = { };
      description = "Non-secret environment for every component; overrides wired values.";
    };

    components = lib.mapAttrs (n: c: {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Run component ${n} (${c.kind}).";
      };
    }) managed;
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = lib.all (n: lib.elem n handled) needs;
        message = "services.${name}: needs ${toString (lib.subtractLists handled needs)} is not set up by the module (recipes/module.md)";
      }
      {
        assertion = cfg.environmentFile == null || !lib.hasPrefix builtins.storeDir cfg.environmentFile;
        message = "services.${name}.environmentFile points into the Nix store: secrets would be world-readable";
      }
    ];

    # Сокет Redis — 660 с группой redis-<project>: доступ только у сервисов проекта.
    users.users.${name} = {
      isSystemUser = true;
      group = name;
      extraGroups = lib.optional (has "redis") "redis-${name}";
    };
    users.groups.${name} = { };

    services = {
      # Peer-аутентификация: системный пользователь = роль = база.
      postgresql = lib.mkIf (has "postgres") {
        enable = true;
        ensureDatabases = [ name ];
        ensureUsers = [ { inherit name; ensureDBOwnership = true; } ];
      };

      # Именованный экземпляр: только unix-сокет (port = 0 по умолчанию).
      redis.servers.${name}.enable = lib.mkIf (has "redis") true;

      rabbitmq.enable = lib.mkIf (has "rabbitmq") true;

      mosquitto = lib.mkIf (has "mqtt") {
        enable = true;
        listeners = [
          {
            address = "127.0.0.1";
            port = 1883;
            omitPasswordAuth = true;
            settings.allow_anonymous = true;
            acl = [ "pattern readwrite #" ];
          }
        ];
      };
    };

    systemd.services = lib.mapAttrs' (n: c: lib.nameValuePair "${name}-${n}" {
      description = "${name}: ${n}";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ] ++ depsOf c;
      requires = depsOf c;
      environment = { HOME = "/var/lib/${name}/${n}"; }
        // lib.mapAttrs (_: wireValue c) c.wire
        // cfg.environment;
      serviceConfig = {
        ExecStart = lib.escapeShellArgs ([ (exe c) ] ++ c.args);
        Type = if c.kind == "job" then "oneshot" else "simple";
        RemainAfterExit = c.kind == "job";
        Restart = if c.kind == "job" then "no" else "on-failure";
        RestartSec = 2;
        User = name;
        Group = name;
        EnvironmentFile = lib.mkIf (cfg.environmentFile != null) cfg.environmentFile;
        StateDirectory = "${name}/${n}";
        WorkingDirectory = "/var/lib/${name}/${n}";
      }
      # Песочница; mkDefault — чтобы проект мог ослабить пункт для одного юнита.
      # MemoryDenyWriteExecute не ставим: ломает cffi, JIT и Node.
      // lib.mapAttrs (_: lib.mkDefault) {
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = !c.gpu;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectKernelLogs = true;
        ProtectControlGroups = true;
        ProtectClock = !c.gpu;              # иначе DeviceAllow закроет /dev/nvidia*
        ProtectHostname = true;
        ProtectProc = "invisible";
        RestrictSUIDSGID = true;
        RestrictNamespaces = true;
        RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
        LockPersonality = true;
        SystemCallArchitectures = "native";
        SystemCallFilter = [ "@system-service" "~@privileged" ];
        CapabilityBoundingSet = "";
        UMask = "0077";
      };
    }) units;
  };
}
```

## Adapting it

- **Variable names and URL schemes come from `wire`** in `lib.components`,
  never from guesses in the module: `ORDERS_DATABASE_URL = "postgres:asyncpg";`
  gives `postgresql+asyncpg:///<project>?host=/run/postgresql`, `"redis:1"`
  gives `unix:///run/redis-<project>/redis.sock?db=1`. Add a new rule kind to
  `wireValue` only when no existing one fits, and document it in
  `nix/components.nix`. A client that cannot speak unix sockets is the only
  reason to give Redis a TCP port (`services.redis.servers.<project>.port`,
  bound to 127.0.0.1 and with `requirePass…`).
- **Arguments** go to `args` (a list), never into `command`:
  `command = "celery"; args = [ "-A" "app" "worker" ];`. The module builds
  `ExecStart` with `escapeShellArgs`, the image puts them into `Entrypoint`.
- **Migrations and seeds** are `kind = "job"` components; services list them in
  `after = [ "migrate" ];` and `depsOf` orders the units. The job's binary ships
  in the component's package (`python.md`, "Migrations").
- **Loosening the sandbox for one unit**: every hardening value is
  `mkDefault`, so override it plainly in `systemd.services.<project>-<n>.serviceConfig`.
  Ports below 1024: `AmbientCapabilities = [ "CAP_NET_BIND_SERVICE" ];
  CapabilityBoundingSet = [ "CAP_NET_BIND_SERVICE" ];`. Never add
  `MemoryDenyWriteExecute` (cffi, JITs, Node break).
- **Frontends** (`kind = "frontend"`): not a unit of their own. Serve the static
  package with `services.caddy`. `handle` blocks are evaluated in order, so the
  API proxy comes before the SPA fallback (a bare `try_files` would rewrite
  `/api/*` to `index.html`):

  ```nix
  services.caddy = lib.mkIf (cfg.components.web.enable or false) {
    enable = true;
    virtualHosts."http://:${toString components.web.port}".extraConfig = ''
      handle /api/* {
        reverse_proxy 127.0.0.1:${toString components.api.port}
      }
      handle {
        root * ${own.web}
        try_files {path} /index.html
        file_server
      }
    '';
  };
  ```

  Mirror the proxy rules of the project's existing nginx/Caddy config, and
  probe the proxied path in `checks.vm` too (`curl …:<web port>/api/health`),
  otherwise a broken proxy passes.
- **S3** (`needs = [ "s3" ]`) and **mongodb** are not set up by the generic
  module; the assertion fails until the project adds them here and appends the
  name to `handled`. S3: `services.garage` (used in Florp_Infra); `minio` is
  marked vulnerable in nixpkgs and does not evaluate. Keys come from
  `environmentFile` or a job that creates them. mongodb is unfree (SSPL): ask
  first.
- **Third-party services without a NixOS module** (vendor images):
  `virtualisation.oci-containers.containers.<n>` with a hashed image
  (`compose-migration.md`). Leave `virtualisation.oci-containers.backend` to
  the host; a project module must not pick docker or podman.
- **GPU components** (`gpu = true`): the module does not enable drivers and
  keeps `PrivateDevices`/`ProtectClock` off for them (both would close
  `/dev/nvidia*`). The host sets `hardware.nvidia`; the VM test and sec-vm
  disable them or run them on CPU when the component supports it.
- **wk projects that deploy to Arch with podman units** (llm-wiki style) keep
  that variant in `deploy/`. The module is an additional variant, not a
  replacement.

## Host usage

```nix
{
  imports = [ inputs.<project>.nixosModules.default ];
  services.<project> = {
    enable = true;
    environmentFile = config.sops.secrets."<project>.env".path;
    environment.LOG_LEVEL = "info";
  };
}
```
