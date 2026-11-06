---
description: Run the full Nix verification gate with the nix-test-runner agent (flake check, niri validate, system build + nvd diff, both HM targets, package checks, VM tests) or add Nix-level tests (flake checks, runNixOSTest, nix-unit). Use before declaring any Nix change done.
argument-hint: "[gate | add <what to test>]"
---

# /nix-test

- No argument or `gate`: invoke **nix-test-runner** to run the gate from the `nix-testing` skill in order and report every command with its tail. Stop at the first failure and hand off to **nix-build-resolver**.
- `add <what>`: invoke **nix-test-runner** to write the test: lint/unit as `checks.<system>.*`, services as `pkgs.testers.runNixOSTest`, pure functions as `nix-unit`, packages as `doCheck`/`passthru.tests`. Then run it.

A green report lists commands and exit codes; skipped checks are named with the reason.
