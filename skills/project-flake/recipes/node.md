# Node: frontends and Node services

References: KRAFTA `frontendImage` (buildNpmPackage + Caddy), hackaton-ic
`nix/web.nix`, FlyBrain `packages.web`, unic/db `dbdocs`.

## Static frontend (Vite, React, Svelte, Vue)

```nix
# nix/web.nix — фронтенд src/web: статическая сборка, раздаёт Caddy/nginx.
{ lib, buildNpmPackage, nodejs_22 }:
let
  src = ../src/web;
in
buildNpmPackage {
  pname = "web";
  version = "0.1.0";
  inherit src;
  nodejs = nodejs_22;
  npmDepsHash = "sha256-…";        # prefetch-npm-deps package-lock.json, или fakeHash
  npmBuildScript = "build";
  # Адреса API — относительные (/api), чтобы один и тот же dist работал везде.
  # VITE_* читаются при сборке: только несекретные значения.
  env.VITE_API_BASE = "/api";
  installPhase = ''
    runHook preInstall
    cp -r dist $out
    runHook postInstall
  '';
  doCheck = true;                   # npm test, если он есть и не требует браузера
  checkPhase = ''
    runHook preCheck
    npm test -- --run
    runHook postCheck
  '';
}
```

- `kind = "frontend"` in `lib.components`, `port` is where the static server
  listens; the module serves it with Caddy (`module.md`), the image uses
  `caddy` (`images.md`).
- pnpm: `stdenv.mkDerivation` with `pnpmDeps = fetchPnpmDeps { … hash = …; }` and
  `pnpmConfigHook` in `nativeBuildInputs` (top-level; `pnpm.fetchDeps`/`pnpm.configHook`
  are deprecated).
  yarn v1: `fetchYarnDeps` + `yarnConfigHook`; yarn berry: `yarn-berry.fetchYarnBerryDeps`
  + `yarn-berry.yarnBerryConfigHook`.
- No lock file: generate one in the devShell (`npm install --package-lock-only`)
  as a separate, reported change; never build without a lock.
- Playwright and browsers come from nixpkgs (`playwright-driver.browsers`,
  `PLAYWRIGHT_BROWSERS_PATH`), not `npx playwright install`
  (`rule-nix-binaries-from-nixpkgs`).
- npm workspaces monorepo (DHNextGenCRM): one `buildNpmPackage` with the root
  lock and `npmWorkspace = "apps/<app>";` per frontend.

## Next.js / SSR or a Node API (a running server, not static)

```nix
{ lib, buildNpmPackage, nodejs_22, makeWrapper }:
buildNpmPackage {
  pname = "site";
  version = "0.1.0";
  # без закоммиченной сборки .next/
  src = lib.fileset.toSource {
    root = ../src/site;
    fileset = lib.fileset.difference ../src/site (lib.fileset.maybeMissing ../src/site/.next);
  };
  npmDepsHash = "sha256-…";
  nodejs = nodejs_22;
  env.NEXT_TELEMETRY_DISABLED = "1";
  # next.config: output: "standalone" — тогда в $out только сервер и его node_modules.
  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/site $out/bin
    cp -r .next/standalone/. $out/share/site/
    cp -r .next/static $out/share/site/.next/static
    cp -r public $out/share/site/public
    makeWrapper ${lib.getExe nodejs_22} $out/bin/site --add-flags $out/share/site/server.js
    runHook postInstall
  '';
  nativeBuildInputs = [ makeWrapper ];
  meta.mainProgram = "site";
}
```

That is a `kind = "service"` with a `port` and `health`, not a frontend.
A committed `.next/` directory is build output: exclude it from `src`
with `lib.fileset`.
