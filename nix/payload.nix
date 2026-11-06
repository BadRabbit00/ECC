# Payload br. Выход:
#   $out/claude/{CLAUDE.md,agents,skills,commands,rules/br,output-styles,br/templates}
#   $out/settings.fragment.json   env + outputStyle, мерджится в ~/.claude/settings.json
#   $out/hooks.json               br:* хуки с путём к запиненному br-hook
{
  lib,
  stdenvNoCC,
  git,
  python,
  brHook,
}:
let
  root = ../.;
  # Только установленные каталоги и tools/ для checkPhase: правка nix/, README, .plan не пересобирает payload.
  src = lib.fileset.toSource {
    inherit root;
    fileset = lib.fileset.unions [
      ../agents
      ../rules
      ../skills
      ../commands
      ../core
      ../output-styles
      ../templates
      ../hooks
      ../tools
      ../agent-models.json
      ../settings.fragment.json
    ];
  };
in
stdenvNoCC.mkDerivation {
  pname = "br-payload";
  version = "0-unstable";
  inherit src;

  dontConfigure = true;
  dontBuild = true;
  nativeBuildInputs = [
    python
    git
  ];

  # Валидатор и все Python-тесты бегут в сборке; красный тест роняет payload.
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    export HOME="$TMPDIR/home"; mkdir -p "$HOME"
    export GIT_AUTHOR_NAME=nix GIT_AUTHOR_EMAIL=nix@localhost GIT_COMMITTER_NAME=nix GIT_COMMITTER_EMAIL=nix@localhost
    python3 -I -B tools/validate.py .
    python3 -I -B -m unittest discover -s tools -p 'test_*.py'
    (cd hooks && python3 -I -B -m unittest discover -s test)
    runHook postCheck
  '';

  installPhase = ''
    runHook preInstall
    c="$out/claude"
    mkdir -p "$c"/{agents,skills,commands,rules/br,output-styles,br/templates}

    cp core/CLAUDE.md "$c/CLAUDE.md"
    cp settings.fragment.json "$out/settings.fragment.json"
    cp output-styles/*.md "$c/output-styles/"
    cp rules/*.md "$c/rules/br/"
    cp -r templates/. "$c/br/templates/"
    cp agents/*.md "$c/agents/"
    cp commands/*.md "$c/commands/"
    cp -r skills/. "$c/skills/"
    chmod -R u+w "$out"

    # Фронтматтер, контракт, hooks.json и самопроверки.
    python3 -I -B ${./payload.py} "$out" "$PWD" ${lib.getExe brHook}
    runHook postInstall
  '';

  meta = {
    description = "br payload for Claude Code: orchestrator style, isolated agents, path rules, br hooks";
    license = lib.licenses.mit;
  };
}
