# Anti-patterns seen in these projects, and what to do instead

| Seen | Why it is wrong | Instead |
|---|---|---|
| `pip install`, `poetry install`, `npm install` in `shellHook` (PsySite, QualysNexus, ComfyUI) | network and mutable state on every `nix develop`; not reproducible | dependencies in Nix (`python.md`, `node.md`) |
| `wget`/`curl` of a model in `shellHook`, no hash (QualysNexus) | unpinned multi-GB download | hashed `fetchurl`, or a path from the environment |
| `import <nixpkgs>` in `docker/default.nix`, `shell.nix` (PsySite, DoctorsHunter) | ignores the lock, impure | inside the flake, `pkgs` from `nixpkgs.legacyPackages` |
| `builtins.getFlake` + `currentSystem`, `--impure` (hackaton-ic `nix/dev.nix`) | impure eval | pass `self`/`system` explicitly |
| `nix build` called from inside an app (hackaton-ic `apps.images`) | build at run time, `unsafeDiscardOutputDependency` | the app depends on the image derivations directly |
| `builtins.readFile ./age.key.txt` | secret copied into the world-readable store | path as a string option, file read at run time |
| token in `docker run -e HF_TOKEN=…` inside `flake.nix` | secret in git and in the store | variable read from the environment; rotate the leaked one |
| tokens in CI YAML | secret in git | CI secrets / environment; rotate |
| `secrets_raw.yaml`, `.keys.txt`, `*.qcow2` tracked | plaintext secrets and huge binaries in git | sops-encrypted file only; `.gitignore`; report to the user |
| `image: x:latest`, `cloudflared:latest` | mutable, unreproducible deploys | content-hash tags; `@sha256:` for third-party |
| Dockerfile with `apt-get` next to a Nix build (PsySite, Alina) | two diverging builds | keep it (variant), offer the Nix image, keep both in sync |
| `LD_LIBRARY_PATH` with `linuxPackages.nvidia_x11` or host CUDA (ComfyUI, lora_training) | tied to one kernel/driver; host toolkit | CUDA from Nix, only `/run/opengl-driver/lib` from the host (`cuda.md`) |
| `devShell = …` singular (AutoHH) | deprecated output | `devShells.<system>.default` |
| no `flake.lock` (Eva-Project-WebUI, GeminiCLI-conf, lora_training) | unpinned inputs | `nix flake lock`, commit it |
| `x86_64-linux` hardcoded in a portable CLI | breaks aarch64 users | `genAttrs` over the supported systems |
| `eachDefaultSystem` for a CUDA-only image (VoiceLM) | outputs that cannot build | list only the systems that work |
| the same flake copied into three repos (BlogAI x3) | drift | share through an input or a template; at least keep them in sync deliberately |
| `doCheck = false` on the whole component | tests silently gone | disable the specific failing upstream test, with a comment and an exit condition (dronessuperpuper `inline-snapshot`) |
| `export $(cat .env \| xargs)`, `set -a` without `set +a` | breaks on quoting; leaks into everything | `set -a; . ./.env; set +a` behind a file check |
| committed build output (`.next/`, `result`, logs, cookie jars) | noise and possible secrets | `.gitignore`, exclude from `src` with `lib.fileset` |
