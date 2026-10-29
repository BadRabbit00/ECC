# ECC рантайм: репозиторий + node_modules в сторе и две точки входа.
#   ecc-run  <script> [args]  скрипты скиллов/команд, только из дерева в сторе
#   ecc-hook <run|post|lifecycle> …  хуки Claude Code вместо `node -e "<резолвер>"`
# Оба с запиненным node/python/bash/git. Выборка скиллов и переписанная
# документация — в payload.nix, раскладка по агентам — в default.nix.
{ lib, pkgs, src, version }:

let
  # src — дерево этого репозитория (self флейка): апстрим affaan-m/ecc плюс
  # модуль badrabbit; version приходит из flake.nix (дата коммита).

  #   config-protection — блокирует правку конфигов линтеров;
  #   mcp-health-check — сам поднимает MCP-серверы для пробы и блокирует вызов;
  #   observe — пишет вход/выход каждого инструмента на диск;
  #   format-typecheck / quality-gate — тянут biome/prettier/tsc через npx;
  #   auto-tmux-dev — молча переписывает `npm run dev` в tmux;
  #   LLM summary — фоново зовёт `claude -p haiku` на компакции и Stop.
  # Любая переменная переопределяется из окружения сессии (см. ecc-hook).
  hookEnv = {
    ECC_HOOK_PROFILE = "standard";
    ECC_GATEGUARD = "off";
    ECC_DISABLED_HOOKS = lib.concatStringsSep "," [
      "pre:config-protection"
      "pre:mcp-health-check"
      "post:mcp-health-check"
      "pre:observe"
      "post:observe:continuous-learning"
      "stop:format-typecheck"
      "post:quality-gate"
      "pre:bash:auto-tmux-dev"
      "stop:desktop-notify"
    ];
    ECC_SKIP_OBSERVE = "1";
    ECC_SKIP_LLM_SUMMARY = "1";
    ECC_CONTEXT_MONITOR_COST_WARNINGS = "off"; # подписка, а не API-биллинг
  };

  nodejs = pkgs.nodejs;
  # Единственная npm-зависимость, до которой доходят хуки, — js-yaml
  # (scripts/lib/project-detect.js из session-start). Остальные (ajv, sql.js,
  # @iarna/toml) нужны CLI-скриптам вроде scripts/ecc.js. devDependencies
  # (eslint, typescript, c8) в рантайме не нужны.
  # package.json несёт overrides и devDependencies (eslint, typescript…), а
  # importNpmLock подменяет спецификации на file:-тарболы — npm видит
  # расхождение с локом и лезет в реестр (EOVERRIDE / ENOTCACHED). Поэтому в
  # сборку уходит обрезанный манифест: только четыре прод-зависимости и
  # записи лока без dev=true. Версии при этом те же, что запинил апстрим.
  packageJson = lib.importJSON "${src}/package.json";
  packageLock = lib.importJSON "${src}/package-lock.json";
  nodeModules = pkgs.importNpmLock.buildNodeModules {
    package = removeAttrs packageJson [ "devDependencies" "overrides" "resolutions" "scripts" ];
    packageLock = packageLock // {
      packages = lib.filterAttrs (_: v: !(v.dev or false)) packageLock.packages // {
        "" = removeAttrs packageLock.packages."" [ "devDependencies" ];
      };
    };
    inherit nodejs;
    derivationArgs = {
      pname = "ecc-node-modules";
      inherit version;
    };
  };

  # skill-comply импортирует yaml; остальные питон-скрипты — чистый stdlib.
  python = pkgs.python3.withPackages (ps: [ ps.pyyaml ]);

  # Всё, что скрипты ECC зовут по имени: git для repo identity, jq/awk/sed в
  # sh-скриптах скиллов, flock (util-linux) в observe.sh, claude — из PATH
  # сессии (writeShellApplication PATH только дополняет).
  runtimeInputs = [ nodejs python pkgs.bash pkgs.git pkgs.jq pkgs.coreutils
                    pkgs.findutils pkgs.gnugrep pkgs.gnused pkgs.gawk pkgs.util-linux pkgs.which ];

  # --- Рантайм-дерево: репозиторий + node_modules ----------------------------
  # Хуки ищут корень по пробам scripts/lib/utils.js и skills/continuous-learning-v2,
  # поэтому дерево остаётся полным (все 311 скиллов), а выборка — в payload ниже.
  root = pkgs.stdenvNoCC.mkDerivation {
    pname = "ecc";
    inherit version src;

    dontConfigure = true;
    dontBuild = true;

    # Апстримные тесты хук-рантайма на том же node, что в обёртках. Часть
    # сьютов требует сеть/HOME/claude — отсекаем по имени.
    doCheck = true;
    nativeCheckInputs = runtimeInputs;
    checkPhase = ''
      runHook preCheck
      export HOME="$TMPDIR/home"; mkdir -p "$HOME"
      ln -s ${nodeModules}/node_modules node_modules
      # Тесты session-end читают worktree через git, а шимы npx/pnpm в тестах
      # форматтеров — через /usr/bin/env, которого в песочнице нет.
      git init -q && git -c user.name=nix -c user.email=nix@localhost add -A \
        && git -c user.name=nix -c user.email=nix@localhost commit -q -m 'nix check'
      substituteInPlace tests/hooks/hooks.test.js \
        --replace-fail '#!/usr/bin/env node' '#!${lib.getExe nodejs}'
      node scripts/ci/validate-hooks.js
      node scripts/ci/validate-agents.js
      node scripts/ci/validate-skills.js
      # Пропущены: statusline (терминальные размеры), insaits (внешний
      # монитор), observer/observe (фоновый claude), context-prompt-suggestions
      # (пересчитывает digest реестра скиллов и ловит собственную запись).
      ECC_TEST_JOBS=4 ECC_TEST_SKIP=ecc-statusline,insaits,observer,observe-,context-prompt-suggestions \
        node tests/run-all.js tests/hooks
      rm -rf node_modules .git
      runHook postCheck
    '';

    installPhase = ''
      runHook preInstall
      mkdir -p "$out"
      # Без песочницы docker/, тестов, переводов, Rust/Python-альфы и картинок:
      # ни хуки, ни команды до них не дотягиваются.
      cp -r . "$out"
      rm -rf "$out"/{docker,tests,ecc2,src,assets,examples,integrations,docs,.github,.git*}
      rm -rf "$out"/.{adal,codebuddy,cursor,gemini,hermes,kimi,kiro,openclaw,opencode,pi,pr,qoder-plugin,qwen,trae,vscode,zed}
      rm -f "$out"/{README.zh-CN.md,install.ps1,install.sh,yarn.lock,ecc_dashboard.py}
      ln -s ${nodeModules}/node_modules "$out/node_modules"
      patchShebangs --build "$out/skills" "$out/scripts" "$out/hooks"
      runHook postInstall
    '';

    meta = {
      description = "ECC agent operating system: skills, agents, rules and hook runtime";
      homepage = "https://github.com/BadRabbit00/ECC";
      license = lib.licenses.mit;
    };
  };

  # --- Точки входа -----------------------------------------------------------
  # ecc-run <script> [args]: исполняет скрипт ТОЛЬКО из дерева в сторе; тип
  # интерпретатора — по расширению. Это тот же `nix shell`, но без registry.
  run = pkgs.writeShellApplication {
    name = "ecc-run";
    inherit runtimeInputs;
    text = ''
      if [ $# -lt 1 ]; then
        echo "usage: ecc-run <script under ${root}> [args...]" >&2
        exit 64
      fi
      script=$(realpath -e -- "$1") || exit 66
      shift
      export CLAUDE_PLUGIN_ROOT=${root} ECC_PLUGIN_ROOT=${root}
      case "$script" in
        ${root}/*.py)                exec python3 "$script" "$@" ;;
        ${root}/*.js|${root}/*.mjs|${root}/*.cjs) exec node "$script" "$@" ;;
        ${root}/*.sh)                exec bash "$script" "$@" ;;
        *)
          echo "ecc-run: only runs .py/.js/.mjs/.cjs/.sh under ${root}" >&2
          exit 64
          ;;
      esac
    '';
  };

  # ecc-hook <run|post|lifecycle> args…: то, что апстрим вшивает в settings.json
  # как `node -e "<резолвер корня>"`. Корень известен статически, резолвер не
  # нужен; переменные профиля — дефолты, окружение сессии их переопределяет.
  hook = pkgs.writeShellApplication {
    name = "ecc-hook";
    inherit runtimeInputs;
    text = ''
      kind=$1; shift
      export CLAUDE_PLUGIN_ROOT=${root} ECC_PLUGIN_ROOT=${root}
      ${lib.concatStringsSep "\n" (lib.mapAttrsToList
        (k: v: ''export ${k}="''${${k}:-${v}}"'') hookEnv)}
      case "$kind" in
        run)       exec node ${root}/scripts/hooks/plugin-hook-bootstrap.js "$@" ;;
        post)      exec node ${root}/scripts/hooks/posttooluse-dispatcher.js "$@" ;;
        lifecycle) exec node ${root}/scripts/hooks/lifecycle-hook-bootstrap.js "$@" ;;
        *) echo "ecc-hook: unknown kind $kind" >&2; exit 64 ;;
      esac
    '';
  };

  runExe = lib.getExe run;
  hookExe = lib.getExe hook;
in
{
  inherit src version root run hook runExe hookExe python nodeModules;
}
