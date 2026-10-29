# Images: dockerTools, distroless

Images are built from the same packages as the module. One image per
deployable unit; several components may share one (API + worker from one
package, like llm-wiki's single image for three services).

## nix/images.nix

```nix
# Образы dockerTools из пакетов компонентов: без Dockerfile и пакетного менеджера.
# Компоненты с одним image делят образ; процесс выбирает команда запуска
# (compose `command:` / --entrypoint), как модуль запускает `command` из пакета.
{ pkgs, project, components, packages }:

let
  inherit (pkgs) lib dockerTools;
  labels = {
    "org.opencontainers.image.source" = "https://github.com/<owner>/<repo>";
  };

  # uid 10001 должен быть в /etc/passwd: getpass.getuser(), libpq и torch его спрашивают.
  nss = dockerTools.fakeNss.override {
    extraPasswdLines = [ "app:x:10001:10001:app:/tmp:/noshell" ];
    extraGroupLines = [ "app:!:10001:" ];
  };

  exe = c: lib.getExe' packages.${c.package}
    (if c.command != null then c.command else packages.${c.package}.meta.mainProgram);

  imageFor = c: dockerTools.buildLayeredImage {
    name = "${project}-${lib.removePrefix "image-" c.image}";
    # tag не задан: он равен хешу содержимого — мутабельного :latest нет.
    contents = [ packages.${c.package} pkgs.cacert pkgs.tzdata nss ];
    extraCommands = "mkdir -m 1777 tmp";
    config = {
      Entrypoint = [ (exe c) ] ++ c.args;
      User = "10001:10001";
      WorkingDir = "/tmp";
      ExposedPorts = lib.optionalAttrs (c.port != null) { "${toString c.port}/tcp" = { }; };
      Env = [
        "HOME=/tmp"
        "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
        "TZDIR=${pkgs.tzdata}/share/zoneinfo"
        "PYTHONUNBUFFERED=1"
      ];
      Labels = labels;
    };
  };

  # Для общего образа точку входа задаёт компонент с портом (сервис), если он есть.
  withImage = lib.filterAttrs (_: c: c.image != null && c.kind != "frontend") components;
  rank = c: if c.port != null then 0 else 1;
  pick = cs: lib.head (lib.sort (a: b: rank a < rank b) cs);
  byImage = lib.groupBy (c: c.image) (lib.attrValues withImage);
in
lib.mapAttrs (_: cs: imageFor (pick cs)) byImage
```

The worker that shares the API image overrides the entrypoint at run time
(compose `command:` or `--entrypoint`), exactly as the module runs
`command` from the same package.

## Frontend image

```nix
image-web = dockerTools.buildLayeredImage {
  name = "<project>-web";
  contents = [ pkgs.caddy dockerTools.fakeNss ];
  extraCommands = "mkdir -m 1777 tmp";
  config = {
    Entrypoint = [ (lib.getExe pkgs.caddy) "run" "--config" "${caddyfile}" "--adapter" "caddyfile" ];
    User = "10001:10001";
    ExposedPorts."8080/tcp" = { };
    Env = [ "XDG_DATA_HOME=/tmp" "XDG_CONFIG_HOME=/tmp" ];
  };
};
```

with `caddyfile = pkgs.writeText "Caddyfile" ''…''` serving
`${packages.web}` on `:8080` (unprivileged port; the host maps 80/443).
Append it to what `images.nix` returns (`… // { image-web = …; }`): the generic
`withImage` skips frontends on purpose. The same `caddyfile` handles `/api/*`
first, then the SPA fallback, exactly like the module (`module.md`).

## Rules

- `buildLayeredImage` by default. `streamLayeredImage` when the image is big
  and only ever loaded (`$(nix build --print-out-paths .#image-<c>) | docker load`): no tarball in
  the store. Never a Dockerfile with `apt-get` for something Nix builds.
- Contents: the package, `cacert`, `tzdata`, `fakeNss`. No shell, no coreutils
  unless the entrypoint is a script (then `writeShellApplication` and its
  `runtimeInputs`, not `bashInteractive`).
- Non-root `User`, writable `/tmp` via `extraCommands`; state goes to volumes.
- No secrets in `Env`, no `.env` in `contents`.
- Labels: `org.opencontainers.image.source` so GHCR links the package.
- Check size: `nix path-info -Sh ./result`. A Python image pulling in gcc or
  `-dev` outputs means a build input leaked into runtime.
- Images exist only on Linux: they are added under
  `lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux` (see `skeleton.md`).
- Existing image attrs (`backendImage`, `container`, `image`) stay; add the
  contract name as an alias next to them.
