# CUDA and ML

The split that works on this machine (RTX 5060 Laptop, sm_120, NixOS; Arch
via nixGL):

- **From Nix:** the CUDA toolkit, cuDNN, NCCL, torch, onnxruntime, llama-cpp,
  everything that is compiled against CUDA.
- **From the host:** only the driver, `libcuda.so` and friends. It ships with
  the kernel module and must match the loaded driver, so no flake can provide
  it. On NixOS it lives in `/run/opengl-driver/lib`.

## nixpkgs with CUDA

One import for all outputs of the system (the Florp/VoiceLM style of
`cudaSupport` in one place, not per package):

```nix
pkgsFor = system: import nixpkgs {
  inherit system;
  config = {
    allowUnfree = true;            # CUDA is unfree: only with the user's consent
    cudaSupport = true;
    # cudaCapabilities не задаём: sm_120 уже в наборе по умолчанию для CUDA >= 12.8,
    # а свой набор меняет хеши всех CUDA-пакетов — мимо cache.nixos-cuda.org,
    # часы сборки torch/llama-cpp (так же решено в nixos-conf, home/generic-linux.nix).
  };
};
```

and in `nixConfig`:

```nix
extra-substituters = [ "https://cache.nixos-cuda.org" ];
extra-trusted-public-keys = [ "cache.nixos-cuda.org:74DUi4Ye579gUqzH4ziL9IyiJBlDpMRn9MBN8oNan9M=" ];
```

The key is the one in nixos-conf `nix.settings.trusted-public-keys`; if it ever
changes, copy it from there, never invent one. Build with `--max-jobs 4 --cores 4`: a cache miss on torch
or llama-cpp is hours of compilation.

## Packages

- Python: `ps.torch` resolves to the CUDA build with `cudaSupport = true`.
  `torch-bin` is an acceptable shortcut (VoiceLM) when the source build is not
  cached; say so in a comment.
- Binaries linking CUDA (C++, Rust candle, Go cgo): add `autoAddDriverRunpath`
  to `nativeBuildInputs`. It writes `/run/opengl-driver/lib` into the RPATH,
  so the program finds `libcuda.so` without `LD_LIBRARY_PATH`.
- Python wheels you do not build (pip/uv wheelhouse): `autoPatchelfHook` plus
  `autoAddDriverRunpath` in the venv derivation.
- Models are data, not dependencies. A model needed by tests or the image is a
  hashed `fetchurl` (BlogAI `packages.embedding-model`); a big model stays
  outside the store and its path comes from the environment (`MODEL_PATH`).
  Never download it from `shellHook` (QualysNexus).

## devShell

```nix
devShells.default = pkgs.mkShell {
  packages = [ python cudaPackages.cuda_nvcc ];
  shellHook = ''
    # Только драйвер с хоста: libcuda.so из модуля ядра. Остальная CUDA — из Nix.
    export LD_LIBRARY_PATH=/run/opengl-driver/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
  '';
};
```

That is the only CUDA-related host path. Not allowed:

- `linuxPackages.nvidia_x11` in `LD_LIBRARY_PATH` (ComfyUI): ties the shell to
  one kernel and driver build;
- `pip install torch --index-url …cu121` into a `.venv` (ComfyUI);
- `cudatoolkit` from the host, or CUDA paths exported by hand (lora_training).

On Arch (standalone Home Manager), the host driver comes through nixGL:
run the shell's programs via the nixGL wrapper that HM already provides
instead of `/run/opengl-driver/lib`.

## Images and the module

- Image `contents` include the CUDA libraries the package needs (they come
  with the package closure); the container runtime injects the driver
  (`--device nvidia.com/gpu=all` with CDI, or `--gpus all`).
- `lib.components.<c>.gpu = true`. The module sets `PrivateDevices = false`
  for it; the host enables `hardware.nvidia`. `checks.vm` and sec-vm have no
  GPU: they disable the component or run it on CPU if it supports a CPU
  fallback (`CUDA_VISIBLE_DEVICES=` and a CPU code path). State in the
  component's comment which one applies.
