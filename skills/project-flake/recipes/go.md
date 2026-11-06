# Go components

References: wk (`package.nix`, coverage gate), Alina/hexlet, hackaton-ic
`nix/core.nix`.

```nix
# nix/gateway.nix — компонент gateway (src/gateway).
{ lib, buildGoModule }:
let
  src = ../src/gateway;
in
buildGoModule {
  pname = "gateway";
  version = "0.1.0";
  src = lib.fileset.toSource {
    root = src;
    fileset = lib.fileset.unions [ (src + "/go.mod") (src + "/go.sum") (src + "/cmd") (src + "/internal") ];
  };
  vendorHash = "sha256-…";     # lib.fakeHash → собрать → вписать хеш из ошибки
  subPackages = [ "cmd/gateway" ];
  env.CGO_ENABLED = 0;
  ldflags = [ "-s" "-w" "-X main.version=0.1.0" ];
  # С subPackages buildGoModule тестирует только эти каталоги — гоняем все пакеты модуля.
  checkPhase = ''
    runHook preCheck
    go test ./...
    runHook postCheck
  '';
  meta.mainProgram = "gateway";
}
```

- `vendor/` committed: `vendorHash = null;`.
- Several binaries in one module: list them in `subPackages`; each becomes a
  `command` in `lib.components` for the same `package`.
- Several modules (`core`, `gateway` each with its own `go.mod`): one
  `nix/<c>.nix` per module.
- `go.work` monorepo: build each module separately anyway; `go.work` is for
  the devShell.
- `vendorHash` changes whenever `go.sum` does: update it in the same commit
  (`rule-deploy-nix-package`).
- Tools (`golangci-lint`, `gopls`, `go`) come from the devShell, not
  `go install` (`rule-nix-go-tools`).
- Static binary image: `contents = [ pkg pkgs.cacert dockerTools.fakeNss ]`;
  no tzdata needed if the code embeds `time/tzdata`.
