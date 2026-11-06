# Python components

Pick the first option that works, in this order. Do not mix two of them for
one component.

| Situation | Recipe |
|---|---|
| All dependencies exist in nixpkgs at acceptable versions | **A. nixpkgs deps** (dronessuperpuper, llm-wiki) |
| `uv.lock` exists and some deps are missing/too old in nixpkgs | **B. uv2nix** (BlogAI) |
| Only `requirements.txt` with `--hash`, deps missing in nixpkgs | **C. wheelhouse** (KRAFTA) |

`pip install`, `poetry install` or a `.venv` created in `shellHook` is never
an option (`rule-nix-shellhook-no-install`).

## A. Dependencies from nixpkgs

One dependency list shared by the devShell and every Python component:

```nix
# nix/python-env.nix — единый список зависимостей (devShell + пакеты).
{ pkgs }:
let
  python = pkgs.python312.override {
    packageOverrides = _final: prev: {
      # Точечные правки пакетов nixpkgs — здесь, с комментарием «почему» и «когда убрать».
    };
  };
in
{
  inherit python;
  runtimeDeps = ps: [ ps.fastapi ps.uvicorn ps.pydantic-settings ps.sqlalchemy ps.asyncpg ps.httpx ];
  testDeps = ps: [ ps.pytest ps.pytest-asyncio ps.respx ];
}
```

```nix
# nix/orders.nix — компонент orders (src/orders), тесты при сборке.
{ lib, pkgs }:
let
  env = import ./python-env.nix { inherit pkgs; };
  ps = env.python.pkgs;
  src = ../src/orders;
  pyproject = builtins.fromTOML (builtins.readFile (src + "/pyproject.toml"));
in
ps.buildPythonApplication {
  pname = "orders";
  version = pyproject.project.version;   # одна версия у тега, кода и пакета
  pyproject = true;
  src = lib.fileset.toSource {
    root = src;
    fileset = lib.fileset.unions [ (src + "/pyproject.toml") (src + "/app") (src + "/tests") ];
  };
  build-system = [ ps.hatchling ];
  dependencies = env.runtimeDeps ps;
  nativeCheckInputs = [ ps.pytestCheckHook ] ++ env.testDeps ps
    ++ [ pkgs.postgresql_16 pkgs.redis ];    # тесты сами поднимают временные БД
  pythonImportsCheck = [ "app" ];
  meta.mainProgram = "orders-api";            # [project.scripts] в pyproject.toml
}
```

- `[project.scripts]` in `pyproject.toml` defines the binaries; every
  `command` in `lib.components` must be one of them.
- No `pyproject.toml` (bare `main.py` + `requirements.txt`): add a minimal
  `pyproject.toml` with `[project.scripts]` (hatchling) rather than a
  `writeShellApplication` around `python main.py`. Tell the user it is new.
- A package missing from nixpkgs: `ps.buildPythonPackage` with `fetchPypi`
  and a hash in `packageOverrides`, as VoiceLM does. More than two or three
  of those: switch to B or C.
- Tests that need the network: mark them in the project (`-m "not network"`)
  and pass `disabledTestMarks = [ "network" ];`; never `doCheck = false`
  for the whole component.

## B. uv2nix (uv.lock)

```nix
inputs = {
  pyproject-nix = { url = "github:pyproject-nix/pyproject.nix"; inputs.nixpkgs.follows = "nixpkgs"; };
  uv2nix = { url = "github:pyproject-nix/uv2nix"; inputs.pyproject-nix.follows = "pyproject-nix"; inputs.nixpkgs.follows = "nixpkgs"; };
  pyproject-build-systems = { url = "github:pyproject-nix/build-system-pkgs"; inputs.pyproject-nix.follows = "pyproject-nix"; inputs.uv2nix.follows = "uv2nix"; inputs.nixpkgs.follows = "nixpkgs"; };
};
```

```nix
# nix/python-env.nix
{ pkgs, uv2nix, pyproject-nix, pyproject-build-systems }:
let
  inherit (pkgs) lib;
  # Корень workspace — каталог с pyproject.toml и uv.lock, не весь репозиторий.
  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ../src/<c>; };
  overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
  pythonSet = (pkgs.callPackage pyproject-nix.build.packages { python = pkgs.python312; })
    .overrideScope (lib.composeManyExtensions [ pyproject-build-systems.overlays.default overlay ]);
in
{
  inherit pythonSet workspace;
  venv = pythonSet.mkVirtualEnv "<project>-env" workspace.deps.default;
}
```

The component package is the venv (`packages.<c> = venv`); its binaries are
the `[project.scripts]`; a venv has no `meta.mainProgram`, so every component
using it sets `command` explicitly. Tests are a separate `checks.<c>-tests` derivation
running pytest against `mkVirtualEnv … workspace.deps.all`. BlogAI's
`checks.tests` is the reference (it also runs `uv lock --check` and ruff).

## C. Hash-pinned wheelhouse (requirements.txt with --hash)

When neither nixpkgs nor uv2nix fits (KRAFTA: mcp 2.x). Two derivations: a
fixed-output download and an offline install.

```nix
wheelhouse = pkgs.stdenvNoCC.mkDerivation {
  name = "<c>-wheelhouse";
  nativeBuildInputs = [ (python.withPackages (ps: [ ps.pip ])) pkgs.cacert ];
  dontUnpack = true;
  SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
  buildPhase = ''
    runHook preBuild
    export HOME=$TMPDIR
    mkdir -p $out
    python -m pip download --require-hashes --only-binary=:all: --no-deps \
      --disable-pip-version-check --no-cache-dir \
      --python-version 3.12 --implementation cp -r ${requirements} -d $out
    runHook postBuild
  '';
  dontInstall = true; dontFixup = true;
  outputHashMode = "recursive"; outputHashAlgo = "sha256";
  outputHash = { x86_64-linux = "sha256-…"; }.${pkgs.stdenv.hostPlatform.system};
};

venv = pkgs.stdenv.mkDerivation {
  name = "<c>-venv";
  dontUnpack = true;
  nativeBuildInputs = [ pkgs.uv pkgs.autoPatchelfHook ];
  buildInputs = [ pkgs.stdenv.cc.cc.lib pkgs.zlib ];   # manylinux-колёса
  buildPhase = ''
    runHook preBuild
    export HOME=$TMPDIR UV_CACHE_DIR=$TMPDIR/uv UV_PYTHON_DOWNLOADS=never
    ${python.interpreter} -m venv --without-pip $out
    uv pip install --python $out/bin/python --no-index --find-links ${wheelhouse} \
      --require-hashes --no-deps --compile-bytecode -r ${requirements}
    runHook postBuild
  '';
  dontInstall = true;
};
```

Then the component is `writeShellApplication` / `makeWrapper` running
`${venv}/bin/python -m <module>` from a source copy, with `meta.mainProgram`.
Every platform the project builds on needs its own `outputHash`; leave
`lib.fakeHash` only for a platform nobody builds, and say so in a comment.

## Migrations (alembic) as a `job` component

The migrations ship in the service's own package, so the job runs the exact
code and dependencies of the service (verified on dronessuperpuper: VM test
applies them and the API answers after). In `nix/<c>.nix`:

```nix
  src = lib.fileset.toSource {
    root = srcDir;
    fileset = lib.fileset.unions [
      (srcDir + "/pyproject.toml") (srcDir + "/alembic.ini")
      (srcDir + "/app") (srcDir + "/migrations") (srcDir + "/tests")
    ];
  };

  # Шаг миграций: alembic из окружения сервиса; wrapPythonPrograms добавит app в sys.path.
  postInstall = ''
    mkdir -p $out/share/<c>
    cp -r alembic.ini migrations $out/share/<c>/
    cat > $out/bin/<c>-migrate <<EOF
    #!${env.python.interpreter}
    import os, sys
    from alembic.config import main
    os.chdir("$out/share/<c>")
    sys.exit(main(argv=["-c", "alembic.ini", "upgrade", "head"]))
    EOF
    chmod +x $out/bin/<c>-migrate
  '';
```

`alembic.ini` must use `script_location = %(here)s/migrations`, and
`migrations/env.py` must read the database URL from the environment (the
`wire`d variable), not from the ini file. Django: the same idea with
`manage.py migrate` as the job's command.
