---
name: nixos-module-patterns
description: "Writing NixOS and Home Manager modules correctly: options with lib.types, config with mkIf/mkMerge/mkDefault/mkForce, assertions and warnings, systemd services and timers, user services bound to the session, home.file/xdg.configFile, activation scripts for mutable files, sops-nix secrets, specialisations. Use when adding or reviewing a .nix module in modules/, hosts/ or home/."
---

# NixOS and Home Manager module patterns

## Shape of a module

```nix
{ config, lib, pkgs, ... }:
let
  cfg = config.services.myThing;
in {
  options.services.myThing = {
    enable = lib.mkEnableOption "my thing";
    port = lib.mkOption {
      type = lib.types.port;
      default = 8080;
      description = "Listening port.";
    };
    settings = lib.mkOption {
      type = (pkgs.formats.toml { }).type;   # structured settings, not strings
      default = { };
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.services.my-thing = { … };
    networking.firewall.allowedTCPPorts = [ cfg.port ];
    assertions = [{
      assertion = cfg.port != 80 || config.services.nginx.enable == false;
      message = "my-thing and nginx both want port 80";
    }];
  };
}
```

- A module that only sets config (no options) can be just `{ config, pkgs, ... }: { … }`. This repo's `modules/core/*.nix` are mostly of that kind.
- One concern per file. Import from `hosts/desktop/default.nix` or `home/default.nix`; do not grow the entry points.

## Merging and priorities

- `lib.mkIf cond { … }` for whole blocks; never `if cond then { … } else { }` at the top level (it breaks merging and recursion).
- `lib.mkMerge [ a b ]` to combine several conditional blocks in one `config`.
- `lib.mkDefault` for values a user should be able to override; `lib.mkForce` only to beat an upstream module's `mkDefault`/plain value; `lib.mkOverride 900` when you need something between.
- `lib.mkBefore` / `lib.mkAfter` for list ordering (PATH-like, `imports`, shell init).
- Lists concatenate, attrsets merge, strings and numbers conflict: two plain definitions of the same string option is the classic "conflicting definition" error; fix with priorities, not by deleting the other module.

## Types to reach for

`types.bool`, `types.str`, `types.lines` (merges by concatenation), `types.int`, `types.port`, `types.path`, `types.package`, `types.enum [ … ]`, `types.nullOr t`, `types.listOf t`, `types.attrsOf t`, `types.submodule { options = … }`, `types.either a b`, `(pkgs.formats.json {}).type` / `.toml` / `.yaml` / `.ini` for config files.

Generate config files with `pkgs.formats.<f> {}` and `.generate "name" value`, not with string templates.

## systemd

```nix
systemd.services.my-thing = {
  description = "…";
  wantedBy = [ "multi-user.target" ];
  after = [ "network-online.target" ];
  wants = [ "network-online.target" ];
  serviceConfig = {
    ExecStart = "${lib.getExe pkg} --port ${toString cfg.port}";
    DynamicUser = true;            # or User/Group
    StateDirectory = "my-thing";   # /var/lib/my-thing
    Restart = "on-failure";
    # hardening baseline
    NoNewPrivileges = true; ProtectSystem = "strict"; ProtectHome = true;
    PrivateTmp = true; ProtectKernelTunables = true; ProtectControlGroups = true;
    RestrictAddressFamilies = [ "AF_INET" "AF_INET6" "AF_UNIX" ];
    CapabilityBoundingSet = "";
  };
  environment = { … };
};
systemd.timers.my-job = { wantedBy = [ "timers.target" ]; timerConfig.OnCalendar = "daily"; };
```

- `lib.getExe pkg` instead of `${pkg}/bin/<guess>`.
- User services in Home Manager: `systemd.user.services.<n>` with `Unit`/`Service`/`Install` attrsets; in this repo bind desktop autostart to `niri.service` (`PartOf`, `After`, `WantedBy = [ "niri.service" ]`), not to `graphical-session.target`.
- `systemd-analyze verify <unit>` and `systemctl --user status` for debugging; `journalctl -u <unit> -b`.

## Home Manager specifics

- `home.file."path".source = ./file` for read-only config: the target becomes a store symlink. If the program **writes** to its own config (Claude's `settings.json`, Codex `config.toml`, Obsidian vault), do **not** own it with `home.file`; merge your part in `home.activation.<name> = lib.hm.dag.entryAfter [ "writeBoundary" ] "…"` with `jq`/`remarshal`, idempotently, like `home/ai/mcp` and `home/ai/ecc` do.
- `home.file."dir" = { source = drv; recursive = true; }` creates a real directory with per-file symlinks (agents that cannot follow a directory symlink need this).
- `xdg.configFile."app/x"` for `~/.config`, `xdg.dataFile` for `~/.local/share`.
- `programs.<x>.enable` modules exist for most tools; prefer them over raw files when they expose the option you need, otherwise `extraConfig`.
- `home.sessionVariables` for env; `home.sessionPath` for PATH.
- `home.stateVersion` is never bumped casually.
- Platform split in this repo: `isNixOS` from `extraSpecialArgs`; wrap NixOS-only pieces in `lib.mkIf isNixOS` and GPU-dependent apps in `gpuWrap`.

## Secrets (sops-nix)

```nix
sops.defaultSopsFile = ../../secrets/secrets.yaml;
sops.age.keyFile = "/var/lib/sops-nix/key.txt";
sops.secrets.my_token = { owner = "myuser"; mode = "0400"; };
# then: /run/secrets/my_token at runtime; EnvironmentFile for systemd; never `builtins.readFile` it.
```

In Home Manager the sops module from `sharedHomeModules` exposes `config.sops.secrets.<n>.path`; wrappers read the path at runtime (see `context7-mcp-sops` in `ai-mcp`).

## Specialisations and boot

- `specialisation.<name>.configuration = { … }` builds a second boot entry sharing everything else (this repo: `ai` specialisation with llama-server).
- `boot.kernelParams`, `boot.kernelModules`, udev rules: never `chmod` driver directories in sysfs from udev (caused EIO at coldplug here in 2026-10). Test boot changes with `nixos-rebuild boot`, keep the previous generation bootable.

## Review checklist for a module

1. `nix flake check --no-build` passes; `nixos-rebuild build --flake .#badrabbitpc` builds; `nvd diff /run/current-system result` shows only the intended changes.
2. Every option has a type and a description; no bare `mkOption {}`.
3. No `mkForce` without a comment saying what it overrides.
4. No secrets or absolute user paths in the file; no `builtins.getEnv`.
5. Services hardened; ports opened explicitly; state under `StateDirectory`.
6. Platform split guarded by `isNixOS`; Arch target still builds (`homeConfigurations."badrabbit@ARCH-BOX"`).
