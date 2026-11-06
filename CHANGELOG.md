# Changelog

## 0.1.0 — 2026-11-06

First standalone release as **warren**. Until now this layer lived as the `badrabbit/` directory and the
`br` payload flavour inside a fork of [ECC](https://github.com/affaan-m/ecc).

- Repository root is the warren layer (internal prefix `br`): `agents/`, `rules/`, `skills/`, `commands/`, `core/`,
  `output-styles/`, `templates/`, `hooks/`, `tools/`.
- Nix: `packages.br-payload`, `packages.br-hook`, `lib.mk { pkgs }`; no Node in the build;
  the validator and the Python test suites run in `checkPhase`.
- Removed: the legacy ECC payload, `ecc-run` / `ecc-hook`, `/astra-review`, the allowlist,
  and every upstream agent, command, hook, rule and skill that the `br` payload flavour did not install.
- Kept from ECC: 22 reference skills (see README, "From ECC").
