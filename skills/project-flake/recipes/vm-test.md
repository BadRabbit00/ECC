# checks.vm: the whole graph boots

One `runNixOSTest` that imports `nixosModules.default`, enables everything
that does not need a GPU, feeds an obviously fake env file and probes every
`health` from `lib.components`. It is the proof that the module is right, and
sec-vm builds its guest the same way.

## nix/vm-test.nix

```nix
# Весь граф в VM: модуль, его зависимости и health каждого компонента.
# Секреты — из .env.example (заглушки из git); переменные из wire задаёт модуль.
{ pkgs, self, project, components }:

let
  inherit (pkgs) lib;
  name = project;
  managedKinds = [ "service" "worker" "job" "frontend" ];
  gpuManaged = lib.filterAttrs (_: c: c.gpu && lib.elem c.kind managedKinds) components;
  active = lib.filterAttrs (_: c: !c.gpu && lib.elem c.kind managedKinds) components;
  probed = lib.filterAttrs (_: c: c.port != null && c.health != null) active;
  units = lib.filterAttrs (_: c: c.kind != "frontend") active;
  wired = lib.unique (lib.concatMap (c: lib.attrNames c.wire) (lib.attrValues components));

  examples = lib.unique (lib.filter (f: f != null) (lib.mapAttrsToList (_: c: c.envExample) components));
  # Только *.example: настоящий .env в тест (и в store) попасть не может.
  checked = map (f: assert lib.assertMsg (lib.hasSuffix ".example" f)
    "components.envExample must be a committed *.example file, got ${f}"; f) examples;
  # KEY=VALUE без переменных из wire: EnvironmentFile сильнее Environment.
  exampleLines = file: lib.filter
    (l: builtins.match "[A-Z_][A-Z0-9_]*=.*" l != null
      && !(lib.elem (lib.head (lib.splitString "=" l)) wired))
    (lib.splitString "\n" (builtins.readFile (../. + "/${file}")));
  fakeEnv = lib.concatStringsSep "\n" (lib.unique (lib.concatMap exampleLines checked));
in
pkgs.testers.runNixOSTest {
  name = "${name}-graph";

  nodes.machine = {
    imports = [ self.nixosModules.default ];
    virtualisation = { memorySize = 2048; diskSize = 4096; };
    environment.etc."${name}.env".text = fakeEnv;
    environment.systemPackages = [ pkgs.curl ];
    services.${name} = {
      enable = true;
      environmentFile = "/etc/${name}.env";
      # Без GPU: такие компоненты выключены (или запускаются на CPU, см. cuda.md).
      components = lib.mapAttrs (_: _: { enable = false; }) gpuManaged;
    };
  };

  testScript = ''
    from datetime import timedelta

    machine.wait_for_unit("multi-user.target")
  '' + lib.concatStrings (lib.mapAttrsToList (n: _: ''
    machine.wait_for_unit("${name}-${n}.service")
  '') units) + lib.concatStrings (lib.mapAttrsToList (n: c: ''
    with subtest("${n} answers on ${c.health}"):
        machine.wait_until_succeeds("curl -fsS http://127.0.0.1:${toString c.port}${c.health}", timeout=timedelta(seconds=120))
  '') probed) + ''
    # Основной сценарий проекта (rule-deploy-verify-artifact) — свой для проекта.
    # Пример для alembic; без alembic замени на свой сценарий, не копируй как есть:
    # with subtest("migrations applied"):
    #     machine.succeed("runuser -u postgres -- psql -d ${name} -tAc 'select count(*) from alembic_version' | grep -qx 1")
  '';
}
```

`gpuManaged` holds only GPU components the module manages (a `gpu = true` CLI
has no `components.<n>` option), so the VM disables exactly those. A frontend
that proxies the API gets one more probe through its own port
(`curl …:<web port>/api/health`): probing the API port directly would pass
with a broken proxy.

## What to add per project

- One `subtest` for the main scenario (`rule-deploy-verify-artifact`): create
  an order, log in with a seeded user, fetch the frontend's index.html.
  Keep it in the same file after the health probes.
- Seeds and migrations: if they are `job` components the module already runs
  them; wait for `${name}-migrate.service` before probing.
- Components that must talk to the internet (payment gateways, SMS, LLM APIs):
  the VM has no network. Point them at a stub (a tiny `pkgs.writers.writePython3Bin`
  HTTP server in the test, or the project's own stub service) through `environment`.
- Heavy graphs: raise `memorySize`, not the number of probes skipped.

## Running

```sh
nix build .#checks.x86_64-linux.vm -L --max-jobs 4 --cores 4
nix run .#checks.x86_64-linux.vm.driverInteractive   # shell into the VM on failure
```
