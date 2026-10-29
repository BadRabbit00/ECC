---
name: nix-testing
description: "Testing Nix code and Nix-built software: the gate sequence (nix flake check, nixos-rebuild build, HM activationPackage, nvd diff), lint/format checks as flake checks, package checkPhase, NixOS VM integration tests (nixosTest / testers.runNixOSTest), nix-unit for pure Nix functions, and validating this repo's niri config. Use when adding tests to a flake, verifying a system change before switching, or when asked whether a Nix change is safe."
---

# Testing with Nix

## The gate sequence for this repository (`~/nixos-conf`)

Run in this order; stop at the first failure.

```bash
git add -A                                   # new files are invisible to Nix otherwise
nix flake check --no-build                   # eval of every output, fast
niri validate --config home/desktop/niri/config.kdl   # only when niri config changed
nixos-rebuild build --flake .#badrabbitpc    # full system, no switch, writes ./result
nvd diff /run/current-system result          # exactly what would change
nix build --impure '.#homeConfigurations."badrabbit@ARCH-BOX".activationPackage' --no-link   # Arch target still builds
```

User layer only (faster when only `home/` changed):

```bash
nix build --impure --no-link --print-out-paths --expr \
  '(builtins.getFlake (toString ./.)).nixosConfigurations.badrabbitpc.config.home-manager.users.BadRabbit.home.activationPackage'
```

Then `sudo nixos-rebuild test --flake .#badrabbitpc` (reversible on reboot) before `switch`.

## Checks inside a flake

```nix
checks.${system} = {
  build = self.packages.${system}.default;                 # the package itself
  lint = pkgs.runCommand "lint" { nativeBuildInputs = [ pkgs.statix pkgs.deadnix pkgs.nixfmt-rfc-style ]; } ''
    cd ${self}
    statix check .
    deadnix --fail .
    nixfmt --check .
    touch $out
  '';
  tests = pkgs.runCommand "tests" { nativeBuildInputs = [ pythonEnv ]; } ''
    cd ${self}
    pytest -q -p no:cacheprovider tests/
    touch $out
  '';
};
```

`nix flake check -L` builds all of them. In CI that is the only command you need.

## Package-level tests

- `doCheck = true` plus `checkPhase` with upstream's test runner; `nativeCheckInputs` for test-only tools (`pytestCheckHook`, `versionCheckHook`).
- `passthru.tests.<name>` for tests that need the built package (e.g. `testers.testVersion { package = pkg; }`), built with `nix build .#pkg.tests.<name>`.
- Sandbox facts: no network, `HOME=/homeless-shelter`, no `/usr/bin/env`. Set `HOME=$TMPDIR`, `patchShebangs` test fixtures, skip suites that need network with a comment naming them.
- Skip tests with `ECC_TEST_SKIP`-style env, never by deleting them from the source.

## NixOS VM integration tests

```nix
checks.${system}.service = pkgs.testers.runNixOSTest {
  name = "my-service";
  nodes.machine = { config, pkgs, ... }: {
    imports = [ self.nixosModules.myService ];
    services.myService.enable = true;
  };
  testScript = ''
    machine.wait_for_unit("my-service.service")
    machine.wait_for_open_port(8080)
    machine.succeed("curl -sf http://localhost:8080/health")
  '';
};
```

- Multi-node: `nodes.server`, `nodes.client`, `client.succeed("curl server")`.
- Interactive debugging: `nix build .#checks.x86_64-linux.service.driverInteractive && ./result/bin/nixos-test-driver` then `start_all(); machine.shell_interact()`.
- Needs KVM (`/dev/kvm`); throttle with `--max-jobs 1` because each VM takes RAM.

## Testing pure Nix functions

- `nix-unit` (`nix shell nixpkgs#nix-unit`): a `tests.nix` with `{ testFoo = { expr = lib.foo 1; expected = 2; }; }` and `nix-unit --flake .#tests`.
- Quick ad hoc: `nix eval --expr 'let lib = (builtins.getFlake "nixpkgs").lib; in lib.foo 1'`.
- Assertions inside modules (`assertions = [ { assertion; message; } ]`) are tests too: they fail evaluation with a readable message.

## Testing the user environment after activation

- `home-manager generations` / `ls -l ~/.local/state/nix/profiles/home-manager*` to confirm the generation.
- Dotfiles: `readlink ~/.config/<app>/<file>` points into `/nix/store`.
- Services: `systemctl --user status <unit>`, `journalctl --user -u <unit> -b`.
- Rollback: run the previous generation's `activate`; system: `sudo nixos-rebuild switch --rollback`.

## What a "tests pass" report must contain

1. The exact commands run and their exit status.
2. For VM tests, the test name and node names.
3. What was skipped and why (sandbox, network, hardware).
4. `nvd diff` summary when a system or HM generation was built.
Never report green from memory; paste the tail of the output.
