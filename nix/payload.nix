# ECC payload (этот форк, см. ../BADRABBIT.md): какие скиллы, агенты, команды и правила попадают в раскладку,
# какие модели стоят у агентов, и переписанная под Nix документация.
# Выход: $out/{claude,codex,agy}/… и $out/hooks.json для ecc-sync.
{ lib, pkgs, runtime }:

let
  inherit (runtime) version root runExe hookExe python;


  # Модули ECC (manifests/install-modules.json). developer = core +
  # framework-language + database + orchestration; security и devops-infra —
  # под профиль Архитектора. Переводы, media, prediction-market и прочее — нет.
  modules = [
    "rules-core"
    "agents-core"
    "commands-core"
    "hooks-runtime"
    "workflow-quality"
    "framework-language"
    "database"
    "orchestration"
    "security"
    "devops-infra"
    "badrabbit"      # свои скиллы: модуль форка BadRabbit00/ECC (ветка badrabbit)
  ];

  # Скиллы, которые на NixOS либо не имеют смысла, либо сами нарушают доктрину.
  excludedSkills = [
    "configure-ecc"           # npx ecc-universal setup — инсталлятор; здесь это этот файл
    "deepseek-harness-setup"  # чужой харнесс
    "windows-desktop-e2e"     # pywinauto/Windows
    "skill-scout"             # gh search + императивная установка в ~/.claude/skills
    "repo-scan"               # git clone в ~/.claude/skills
    "unified-memory"          # требует npm install -g ecc-universal
    "flox-environments"       # конкурент Nix
    "plankton-code-quality"   # brew install
    "design-system"           # уже есть из ui-ux-pro-max (ai-skills), богаче
  ];

  # Команды-обёртки, которым нечего делать без апстримного инсталлятора.
  excludedCommands = [ "auto-update" ];
  # Команды, которых не должно быть у Codex: ask-astra/write-astra зовут Codex сам.
  codexExcludedCommands = [ "ask-astra" "write-astra" ];

  # Модель и effort каждого агента для трёх CLI. Апстрим ставит алиасы
  # (sonnet/opus), которые съезжают вместе с дефолтами; здесь полные ID.
  #   claude — model/effort в frontmatter ~/.claude/agents/<n>.md
  #   codex  — model/model_reasoning_effort в ~/.codex/agents/<n>.toml
  #   agy    — только тир (inherit|flash_lite|flash|pro) в ~/.gemini/config/agents/<n>.md;
  #            полный ID agy молча отбрасывает вместе с файлом, effort на агента
  #            не ставится (берётся из сессии: agy --effort / /effort).
  # Схема Архитектора: ревью, безопасность, рефакторинг, сборка — Opus 5.5 /
  # Astra; кодинг — Sonnet 5.5 / Sol 6.1; механика — Haiku 5.5 / Luna; в Codex
  # везде минимум high; security-reviewer и architect — Fable 5.1 / Astra xhigh;
  # тяжёлые языки (rust, cpp) — xhigh. В agy тир pro (Argon) только для
  # безопасности, архитектуры и глубокого рефакторинга, остальное flash (3.8),
  # механика flash_lite.
  # Сборка payload падает, если агент из таблицы пропал или у какого-то агента
  # после подстановки нет model/effort (новый агент в апстриме → дописать сюда).
  agentModels =
    let
      cls = cm: ce: xm: xe: tier: { inherit cm ce xm xe tier; };
      fable   = cls "claude-fable-5-1"  "medium" "gpt-6-astra" "xhigh" "pro";
      opusX   = cls "claude-opus-5-5"   "xhigh"  "gpt-6-astra" "xhigh" "flash";
      opusH   = cls "claude-opus-5-5"   "high"   "gpt-6-astra" "high"  "flash";
      opusM   = cls "claude-opus-5-5"   "medium" "gpt-6-astra" "high"  "flash";
      sonnetH = cls "claude-sonnet-5-5" "high"   "gpt-6.1-sol" "high"  "flash";
      sonnetM = cls "claude-sonnet-5-5" "medium" "gpt-6.1-sol" "high"  "flash";
      haikuH  = cls "claude-haiku-5-5"  "high"   "gpt-6-luna"  "high"  "flash_lite";
      haikuM  = cls "claude-haiku-5-5"  "medium" "gpt-6-luna"  "high"  "flash_lite";
      many = v: names: lib.genAttrs names (_: v);
    in
    many fable [ "security-reviewer" "architect" ]
    // many opusX [ "rust-reviewer" "cpp-reviewer" "rust-build-resolver" "cpp-build-resolver" "nix-reviewer" "nix-build-resolver" ]
    // many opusH [
      # ревьюеры
      "code-reviewer" "database-reviewer" "python-reviewer" "fastapi-reviewer" "django-reviewer"
      "go-reviewer" "typescript-reviewer" "react-reviewer" "vue-reviewer" "kotlin-reviewer"
      "flutter-reviewer" "swift-reviewer" "java-reviewer" "csharp-reviewer" "fsharp-reviewer"
      "php-reviewer" "ruby-reviewer" "mle-reviewer" "rag-pipeline-reviewer" "healthcare-reviewer"
      "bengali-reviewer" "network-config-reviewer"
      # ревью-помощники
      "silent-failure-hunter" "pr-test-analyzer" "type-design-analyzer" "gan-evaluator"
      # рефакторинг
      "code-simplifier" "performance-optimizer"
      # сборка (общий)
      "build-error-resolver"
      # планирование
      "planner" "code-architect" "spec-miner" "nix-architect"
    ]
    // { refactor-cleaner = opusH // { tier = "pro"; }; }   # глубокий рефакторинг → Argon
    // many opusM [ "agent-evaluator" "gan-planner" ]
    // many sonnetH [
      "tdd-guide" "gan-generator" "harmonyos-app-resolver" "nix-engineer" "nix-test-runner"
      "kotlin-build-resolver" "java-build-resolver" "swift-build-resolver" "pytorch-build-resolver"
    ]
    // many sonnetM [
      "e2e-runner" "code-explorer" "commit-reviewer" "loop-operator" "harness-optimizer"
      "opensource-sanitizer" "a11y-architect" "homelab-architect" "network-architect"
      "network-troubleshooter" "chief-of-staff" "marketing-agent" "seo-specialist"
      "go-build-resolver" "dart-build-resolver" "django-build-resolver" "react-build-resolver"
    ]
    // many haikuH [ "doc-updater" "docs-lookup" ]
    // many haikuM [ "comment-analyzer" "conversation-analyzer" "opensource-forker" "opensource-packager" ];

  agentModelTable = pkgs.writeText "ecc-agent-models.tsv" (lib.concatStrings
    (lib.mapAttrsToList (n: v: "${n}\t${v.cm}\t${v.ce}\t${v.xm}\t${v.xe}\t${v.tier}\n") agentModels));

  # Хуки: профиль standard, но без того, что мешает одному разработчику на Nix.
  #   GateGuard — отклоняет первый Edit каждого файла и первый Bash за сессию;

  # --- Nix-баннер для документации --------------------------------------------
  nixBanner = pkgs.writeText "ecc-nix-banner.md" ''
    > **NixOS environment (local adaptation of this ECC file).** This machine is
    > NixOS and everything is declarative. Before following any command below:
    > - Run project tooling inside the project's devShell: `nix develop -c <cmd>`
    >   (or under direnv). One-off tools: `nix shell nixpkgs#<pkg> -c <cmd>`.
    >   Never assume a bare `python`, `node`, `npx`, `uv`, `cargo`, `go` on PATH.
    > - Never install into the system: no `pip install`, `npm install -g`, `pipx`,
    >   `cargo install`, `uv tool install`, `brew`, `apt`, `curl | sh`. Declare the
    >   dependency in the project's `flake.nix` devShell (or in the lockfile the
    >   flake consumes) and find packages with `nix search nixpkgs <name>`.
    > - No inline interpreters (`python -c`, `node -e`, long `bash -c`): write a
    >   script file and run it through the devShell.
    > - Containers are built with `pkgs.dockerTools.buildLayeredImage` (distroless
    >   contents, no shell), not hand-written `Dockerfile`s with `apt-get`.
    > - Heavy builds: `nix build --max-jobs 4 --cores 4` so 24 cores do not swap.
    > - New files must be `git add`ed before Nix sees them. System changes go into
    >   `~/nixos-conf` and `sudo nixos-rebuild switch --flake .#badrabbitpc`, never into `/etc`.
    > - Scripts that ship with ECC run only through the pinned `ecc-run` wrapper;
    >   secrets reach the devShell from sops-nix, never hardcoded or committed.
    > - Nix work has its own toolkit: `/nix-plan`, `/nix-write`, `/nix-build`, `/nix-test`,
    >   `/nix-review`, `/nix-fix`, agents `nix-architect`/`nix-engineer`/`nix-reviewer`/
    >   `nix-build-resolver`/`nix-test-runner`, skills `nix-toolkit`, `nix-packaging`.
    >
    > Wherever the text below says `pip install`, `npm i -g`, `brew install`,
    > `npx -y …` or `uv run`, read it as "declare it in the flake and run it in
    > `nix develop`".
  '';

  # --- Payload: выборка по модулям + переписанная документация -----------------
  payload = pkgs.stdenvNoCC.mkDerivation {
    pname = "ecc-payload";
    inherit version;
    src = root;

    dontConfigure = true;
    dontBuild = true;
    nativeBuildInputs = [ pkgs.jq pkgs.gnused pkgs.gawk ];

    installPhase = ''
      runHook preInstall
      mkdir -p "$out"/claude/{skills,agents,commands,rules/ecc} "$out"/codex/{skills,prompts,agents} "$out"/agy/agents

      # Какие скиллы попадают в выборку: paths модулей из манифеста минус
      # исключения. Манифест — источник правды, список скиллов не дублируем.
      jq -r --argjson mods '${builtins.toJSON modules}' \
        '.modules[] | select(.id as $id | $mods | index($id)) | .paths[] | select(startswith("skills/")) | ltrimstr("skills/")' \
        manifests/install-modules.json | sort -u > selected-skills
      for s in ${lib.escapeShellArgs excludedSkills}; do sed -i "/^$s\$/d" selected-skills; done
      while read -r s; do
        [ -d "skills/$s" ] || { echo "manifest lists missing skill: $s" >&2; exit 1; }
        cp -r "skills/$s" "$out/claude/skills/$s"
      done < selected-skills
      echo "ECC skills selected: $(wc -l < selected-skills)"

      cp agents/*.md "$out/claude/agents/"
      cp commands/*.md "$out/claude/commands/"
      for c in ${lib.escapeShellArgs excludedCommands}; do rm "$out/claude/commands/$c.md"; done

      # Модель и effort в frontmatter каждого агента (таблица agentModels выше).
      while IFS=$'\t' read -r name model effort _xm _xe _tier; do
        f="$out/claude/agents/$name.md"
        [ -f "$f" ] || { echo "agentModels lists missing agent: $name" >&2; exit 1; }
        awk -v model="$model" -v effort="$effort" '
          BEGIN { fm = 0 }
          /^---[[:space:]]*$/ { fm++; if (fm == 2) { print "model: " model; print "effort: " effort } print; next }
          fm == 1 && /^(model|effort):/ { next }
          { print }
        ' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
      done < ${agentModelTable}
      for f in "$out"/claude/agents/*.md; do
        awk '/^---[[:space:]]*$/ { fm++; next } fm == 1' "$f" | grep -q '^model: claude-' \
          || { echo "agent without pinned model (add to agentModels): $f" >&2; exit 1; }
        awk '/^---[[:space:]]*$/ { fm++; next } fm == 1' "$f" | grep -q '^effort: ' \
          || { echo "agent without effort (add to agentModels): $f" >&2; exit 1; }
      done
      cp -r rules/. "$out/claude/rules/ecc/"
      cp LICENSE "$out/LICENSE"
      cp ${./ECC-GUIDE.md} "$out/ECC-GUIDE.md"
      chmod -R u+w "$out"

      # Скрипты скиллов живут и исполняются из дерева в сторе через ecc-run;
      # копии в ~/.claude/skills — только справочник. Убираем, чтобы агент не
      # запустил их голым интерпретатором. Шаблоны/данные остаются.
      find "$out/claude/skills" -type f \( -name '*.py' -o -name '*.sh' -o -name '*.js' -o -name '*.mjs' -o -name '*.cjs' \) -delete
      find "$out/claude/skills" -type d -empty -delete

      # ---- Переписывание документации ---------------------------------------
      mds=$(find "$out/claude" -name '*.md')
      # 1. Плагинный неймспейс `ecc:planner` -> `planner` (как install-apply).
      sed -E -i 's/(^|[^A-Za-z0-9_@.-])ecc:([a-z][a-z0-9-]*)/\1\2/g' $mds
      # 2. Пути к скриптам -> ecc-run + стор. Формы из апстрима:
      #    python3 "''${CLAUDE_PLUGIN_ROOT}/skills/…", node "$HOME/.claude/skills/ck/…",
      #    bash ~/.claude/skills/<s>/scripts/…, python3 skills/<s>/…,
      #    node scripts/<x>.js (только существующие в дереве скрипты),
      #    а внутри скилла — node "$SKILL_DIR/…", node <skill-dir>/… .
      {
        printf '%s\n' \
          's#(python3?|node|bash) ("?)\$\{?CLAUDE_PLUGIN_ROOT\}?/#${runExe} \2${root}/#g' \
          's#(python3?|node|bash) ("?)(\$HOME|~)/\.claude/skills/#${runExe} \2${root}/skills/#g' \
          's#(python3?|node|bash) (\./)?skills/([a-z0-9-]+)/#${runExe} ${root}/skills/\3/#g' \
          's#\$\{?CLAUDE_PLUGIN_ROOT\}?/#${root}/#g' \
          's#~/\.claude/rules/(common|[a-z-]+)/#~/.claude/rules/ecc/\1/#g' \
          's#(\$HOME|~)/\.claude/skills/([a-z0-9-]+)/(scripts|commands|hooks)/#${root}/skills/\2/\3/#g'
        for f in scripts/*.js scripts/*.mjs scripts/*.sh scripts/hooks/*.js scripts/ci/*.js scripts/codex/*.js scripts/codex/*.sh scripts/dsh/*.js; do
          echo "s#(python3?|node|bash) (\\./)?$f\\b#${runExe} ${root}/$f#g"
        done
      } > rewrite.sed
      sed -E -i -f rewrite.sed $mds
      for d in "$out"/claude/skills/*/; do
        skill=$(basename "$d")
        find "$d" -name '*.md' -exec sed -E -i \
          -e "s#(python3?|node|bash) (\"?)\\\$\{?SKILL_DIR\}?/#${runExe} \\2${root}/skills/$skill/#g" \
          -e "s#(python3?|node|bash) (\"?)<(skill-dir|installed-skill|native-skill-dir|docs-governance-skill)>/#${runExe} \\2${root}/skills/$skill/#g" \
          -e "s#\\\$\{?SKILL_DIR\}?/#${root}/skills/$skill/#g" \
          {} +
      done

      # 3. Точечные правки скиллов, которые тянут зависимости мимо Nix.
      ss="$out/claude/skills"
      # skill-comply: пакет запускается как модуль из каталога скилла.
      sed -E -i 's#uv run python -m scripts\.run#(cd ${root}/skills/skill-comply \&\& ${python}/bin/python3 -m scripts.run)#g' "$ss/skill-comply/SKILL.md"
      # skill-stocktake: results.json лежал внутри скилла; стор read-only.
      sed -E -i 's#~/\.claude/skills/skill-stocktake/results\.json#"''${XDG_STATE_HOME:-$HOME/.local/state}/ecc/skill-stocktake-results.json"#g' "$ss/skill-stocktake/SKILL.md"
      # delivery-gate: копировать хук в ~/.claude/scripts не нужно.
      sed -E -i \
        -e 's#python3 ~/\.claude/scripts/quality-gate\.py#${runExe} ${root}/skills/delivery-gate/hooks/quality-gate.py#g' \
        -e '/^(mkdir -p ~\/\.claude\/scripts|cp skills\/delivery-gate\/hooks\/quality-gate\.py)/d' \
        -e '/^```bash$/{N;/^```bash\n```$/d}' \
        "$ss/delivery-gate/SKILL.md"
      # frontend-slides: export-pdf.sh качает playwright+chromium через npm.
      sed -E -i 's#bash scripts/export-pdf\.sh <path-to-html> \[output\.pdf\] \[--compact\]#nix shell nixpkgs\#chromium -c chromium --headless --no-sandbox --print-to-pdf=output.pdf file://<path-to-html>  (export-pdf.sh is not shipped: it npm-installs playwright at run time)#g' \
        "$ss/frontend-slides/SKILL.md"
      # security-scan (скилл и команда): AgentShield — npm-пакет, не в nixpkgs.
      sed -E -i 's#npm install -g ecc-agentshield#\# ecc-agentshield is not packaged in nixpkgs; run it only from a project devShell that pins it (`nix develop -c npx ecc-agentshield …`)#g' \
        "$ss/security-scan/SKILL.md" "$out/claude/commands/security-scan.md"
      # astra-review: ищет свой скрипт по четырём путям; у нас он один.
      sed -E -i \
        -e '/^ASTRA=""$/,/^\[ -n "\$ASTRA" \]/c\ASTRA=${root}/scripts/astra-review.js' \
        -e 's#node "\$ASTRA"#${runExe} "$ASTRA"#g' \
        "$out/claude/commands/astra-review.md"
      # Упоминания переменных плагина в прозе — без фигурных скобок, чтобы агент не
      # пытался их разыменовать: здесь их не существует.
      sed -E -i 's/`\$\{(CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR)\}`/`\1`/g' $mds

      # 4. Баннер Nix-доктрины после frontmatter в каждом SKILL.md, команде и
      #    агенте (сабагент не видит системную инструкцию, зато читает свой
      #    файл), отдельное always-on правило и вводная для codex.
      for f in $(find "$out/claude/skills" -name SKILL.md) "$out"/claude/commands/*.md "$out"/claude/agents/*.md; do
        awk -v banner="$(cat ${nixBanner})" '
          BEGIN { fm = 0; done = 0 }
          { print }
          !done && /^---[[:space:]]*$/ { fm++; if (fm == 2) { print ""; print banner; done = 1 } }
          END { if (!done) { print ""; print banner } }
        ' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
      done
      cp ${./nix-first.md} "$out/claude/rules/ecc/common/nix-first.md"
      # README правил Claude Code тоже подхватит как правило — он не нужен.
      rm -f "$out/claude/rules/ecc/README.md"

      # ---- Контроль: ни одной ссылки на голый интерпретатор у скриптов ECC ----
      {
        printf '%s\n' '\$\{?CLAUDE_PLUGIN_ROOT' '\$\{?SKILL_DIR' '<skill-dir>' '\.claude/skills/[a-z0-9-]+/(scripts|commands|hooks)/' '\b(python3?|node|bash) +(\./)?skills/'
        for f in scripts/*.js scripts/*.mjs scripts/*.sh scripts/hooks/*.js scripts/ci/*.js scripts/codex/*.js scripts/codex/*.sh scripts/dsh/*.js; do
          echo "\\b(python3?|node|bash) +(\\./)?$f\\b"
        done
      } > forbidden.re
      if grep -rnE -f forbidden.re "$out/claude" --include='*.md' | grep -v '${runExe}' | grep -v '${root}/'; then
        echo "unwrapped ECC script invocations left in the docs" >&2
        exit 1
      fi

      # ---- Codex ---------------------------------------------------------------
      cp -r "$out/claude/skills/." "$out/codex/skills/"
      cp .codex/agents/*.toml "$out/codex/agents/"
      # Три апстримные роли ECC — на ту же схему (минимум high).
      sed -i -e 's/^model = .*/model = "gpt-6.1-sol"/' -e 's/^model_reasoning_effort = .*/model_reasoning_effort = "high"/' "$out/codex/agents/explorer.toml"
      sed -i -e 's/^model = .*/model = "gpt-6-astra"/'  -e 's/^model_reasoning_effort = .*/model_reasoning_effort = "high"/' "$out/codex/agents/reviewer.toml"
      sed -i -e 's/^model = .*/model = "gpt-6-luna"/'   -e 's/^model_reasoning_effort = .*/model_reasoning_effort = "high"/' "$out/codex/agents/docs-researcher.toml"
      # Каждый агент Claude -> роль Codex (~/.codex/agents/<n>.toml, ищется по
      # name) и агент agy (~/.gemini/config/agents/<n>.md). Тело (с Nix-баннером)
      # становится developer_instructions / системным промптом. tools не
      # переносим: имена инструментов у каждого CLI свои, agy на чужом имени виснет.
      while IFS=$'\t' read -r name _cm _ce xm xe tier; do
        f="$out/claude/agents/$name.md"
        desc=$(awk '/^---[[:space:]]*$/{c++; next} c==1 && /^description:/{sub(/^description:[ ]*/,""); print; exit}' "$f" \
          | sed -E "s/^\"(.*)\"$/\1/; s/^'(.*)'$/\1/")
        [ -n "$desc" ] || { echo "agent without description: $name" >&2; exit 1; }
        body=$(awk '/^---[[:space:]]*$/{c++; next} c>=2' "$f")
        case "$body" in *"''''"*) echo "agent body contains '''' (TOML literal string): $name" >&2; exit 1;; esac
        { printf 'name = "%s"\n' "$name"
          printf 'description = %s\n' "$(jq -Rn --arg d "$desc" '$d')"
          printf 'model = "%s"\nmodel_reasoning_effort = "%s"\n\n' "$xm" "$xe"
          printf "developer_instructions = ''''\n%s\n''''\n" "$body"
        } > "$out/codex/agents/$name.toml"
        { printf -- '---\nname: %s\ndescription: %s\nmodel: %s\nsubagent: true\nmainAgent: true\n---\n\n' \
            "$name" "$(jq -Rn --arg d "$desc" '$d')" "$tier"
          printf '%s\n' "$body"
        } > "$out/agy/agents/$name.md"
      done < ${agentModelTable}
      echo "Codex roles: $(command ls "$out/codex/agents" | wc -l), agy agents: $(command ls "$out/agy/agents" | wc -l)"
      for c in ${lib.escapeShellArgs codexExcludedCommands}; do
        [ -f "$out/claude/commands/$c.md" ] || { echo "codexExcludedCommands lists missing command: $c" >&2; exit 1; }
      done
      for c in ${lib.escapeShellArgs codexExcludedCommands}; do
        [ -f "$out/claude/commands/$c.md" ] || { echo "codexExcludedCommands lists missing command: $c" >&2; exit 1; }
      done
      # Команды -> ~/.codex/prompts/ecc-<cmd>.md, как legacy sync: без frontmatter.
      for f in "$out"/claude/commands/*.md; do
        name=$(basename "$f" .md)
        case " ${lib.concatStringsSep " " codexExcludedCommands} " in *" $name "*) continue ;; esac
        { printf '# /%s (ECC command)\n\n' "$name"
          awk 'BEGIN{fm=0} /^---[[:space:]]*$/ && fm<2 {fm++; next} fm==2 || fm==0 {print}' "$f"
        } > "$out/codex/prompts/ecc-$name.md"
      done
      # AGENTS.md: корневой + Codex-дополнение + Nix-правило.
      { cat AGENTS.md
        printf '\n\n---\n\n# Codex Supplement (From ECC .codex/AGENTS.md)\n\n'
        cat .codex/AGENTS.md
        printf '\n\n---\n\n'
        cat ${./nix-first.md}
        printf '\n\n---\n\n'
        cat ${./ECC-GUIDE.md}
      } | sed -E \
          -e 's/(^|[^A-Za-z0-9_@.-])ecc:([a-z][a-z0-9-]*)/\1\2/g' \
          -e 's#`\.agents/skills/`#`~/.codex/skills/` (selected ECC skills, managed by Nix)#g' \
        > "$out/codex/AGENTS.md"

      # ---- Хуки для settings.json ---------------------------------------------
      # Из hooks.json берём событие/matcher/timeout/async и хвост команды после
      # inline-резолвера, из hooks.metadata.json — id и описание (их же пишет
      # install-apply, по ним activation-скрипт узнаёт свои записи).
      jq -n --slurpfile h hooks/hooks.json --slurpfile m hooks/hooks.metadata.json \
         --arg exe ${hookExe} '
        ($h[0].hooks | to_entries) as $events
        | reduce $events[] as $ev ({};
            ($m[0].entries[$ev.key] // error("no metadata for \($ev.key)")) as $meta
            | if ($meta | length) != ($ev.value | length) then error("metadata/hooks length mismatch for \($ev.key)") else . end
            | .[$ev.key] = [ range($ev.value | length) as $i
                | $ev.value[$i] as $e
                | $e.hooks[0] as $cmd
                | ($cmd.command
                   | if test("lifecycle-hook-bootstrap") then "lifecycle"
                     elif test("posttooluse-dispatcher") then "post"
                     else "run" end) as $kind
                | ($cmd.command | sub("^node -e \"[^\"]*\" "; "")) as $rest
                | ($cmd | del(.command) | .command = "\($exe) \($kind) \($rest)") as $hook
                | { id: $meta[$i].id, description: $meta[$i].description, hooks: [ $hook ] }
                  + (if $e.matcher != null then { matcher: $e.matcher } else {} end)
              ])
        | { hooks: . }' > "$out/hooks.json"
      # Ни одна команда не должна содержать апстримный inline-резолвер.
      if grep -q 'require(' "$out/hooks.json"; then
        echo "hook command still carries the inline resolver" >&2; exit 1
      fi
      runHook postInstall
    '';
  };
in
payload
