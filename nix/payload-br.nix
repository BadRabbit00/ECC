# ECC payload, flavour `br` (badrabbit/, see badrabbit/README.md and ECC-REWRITE-PLAN).
# Next to the legacy payload.nix, not instead of it: nixos-conf picks one with ecc.flavour.
# Output:
#   $out/claude/{CLAUDE.md,agents,skills,commands,rules/br,output-styles,br/templates}
#   $out/settings.fragment.json   env + outputStyle, merged into ~/.claude/settings.json
#   $out/hooks.json               br:* hooks with the pinned br-hook wrapper
# No Nix-doctrine banner (core/subagent-contract.md replaces it), no codex/agy export yet.
{ lib, pkgs, runtime }:

let
  inherit (runtime) version root runExe brHookExe python src;

  # badrabbit/ as its own store path: editing it rebuilds only this payload and br-hook.
  br = builtins.path { path = src + "/badrabbit"; name = "badrabbit"; };
  allow = lib.importJSON (br + "/allowlist.json");

  # Upstream ECC scripts that skills/commands may call; rewritten to ecc-run (same rules as payload.nix).
  scriptGlobs = "scripts/*.js scripts/*.mjs scripts/*.sh scripts/hooks/*.js scripts/ci/*.js scripts/codex/*.js scripts/codex/*.sh scripts/dsh/*.js";

  payload = pkgs.stdenvNoCC.mkDerivation {
    pname = "ecc-payload-br";
    inherit version;
    src = root;

    dontConfigure = true;
    dontBuild = true;
    nativeBuildInputs = [ python pkgs.gnused pkgs.gawk pkgs.git pkgs.findutils pkgs.gnugrep ];

    # Validator and all br test suites run inside the build; a red test fails the payload.
    doCheck = true;
    checkPhase = ''
      runHook preCheck
      export HOME="$TMPDIR/home"; mkdir -p "$HOME"
      export GIT_AUTHOR_NAME=nix GIT_AUTHOR_EMAIL=nix@localhost GIT_COMMITTER_NAME=nix GIT_COMMITTER_EMAIL=nix@localhost
      cp -r ${br} "$TMPDIR/br" && chmod -R u+w "$TMPDIR/br"
      python3 -I -B "$TMPDIR/br/tools/validate.py" "$TMPDIR/br" --repo ${src}
      (cd "$TMPDIR/br/tools" && python3 -B -m unittest -q test_validate test_measure_tokens)
      python3 -B -m unittest discover -q -s "$TMPDIR/br/hooks/test" -t "$TMPDIR/br/hooks/test"
      runHook postCheck
    '';

    installPhase = ''
      runHook preInstall
      c="$out/claude"
      mkdir -p "$c"/{agents,skills,commands,rules/br,output-styles,br/templates}

      cp ${br}/core/CLAUDE.md "$c/CLAUDE.md"
      cp ${br}/settings.fragment.json "$out/settings.fragment.json"
      cp ${br}/output-styles/*.md "$c/output-styles/"
      cp ${br}/rules/*.md "$c/rules/br/"
      cp -r ${br}/templates/. "$c/br/templates/"

      # Agents: br agents + allowlisted fork agents (the fork's nix-reviewer is replaced by br's).
      cp ${br}/agents/*.md "$c/agents/"
      for a in ${lib.escapeShellArgs allow.agents}; do
        [ -e "$c/agents/$a.md" ] && { echo "agent $a exists in badrabbit/agents and the allowlist" >&2; exit 1; }
        cp "agents/$a.md" "$c/agents/"
      done

      # Skills: fork + upstream from the tree, then br skills; a name clash fails the build.
      for s in ${lib.escapeShellArgs (allow.skills ++ allow.upstreamSkills)}; do
        [ -d "skills/$s" ] || { echo "allowlisted skill missing: $s" >&2; exit 1; }
        [ -e "$c/skills/$s" ] && { echo "duplicate skill: $s" >&2; exit 1; }
        cp -r "skills/$s" "$c/skills/$s"
      done
      chmod -R u+w "$c"
      # Scripts run from the store through ecc-run; the copies are reference only.
      with_scripts=$(find "$c/skills" -type f \( -name '*.py' -o -name '*.sh' -o -name '*.js' -o -name '*.mjs' -o -name '*.cjs' \) \
        | sed -E "s#^$c/skills/([^/]+)/.*#\1#" | sort -u | tr '\n' ' ')
      echo "upstream/fork skills that carried scripts: ''${with_scripts:-none}"
      find "$c/skills" -type f \( -name '*.py' -o -name '*.sh' -o -name '*.js' -o -name '*.mjs' -o -name '*.cjs' \) -delete
      find "$c/skills" -type d -empty -delete
      for d in ${br}/skills/*/; do
        s=$(basename "$d")
        [ -e "$c/skills/$s" ] && { echo "br skill $s clashes with an allowlisted skill" >&2; exit 1; }
        cp -r "$d" "$c/skills/$s"
      done

      # Commands: allowlisted fork commands + br commands.
      for x in ${lib.escapeShellArgs allow.commands}; do
        [ -f "commands/$x.md" ] || { echo "allowlisted command missing: $x" >&2; exit 1; }
        cp "commands/$x.md" "$c/commands/"
      done
      for f in ${br}/commands/*.md; do
        [ -e "$c/commands/$(basename "$f")" ] && { echo "br command $(basename "$f") clashes" >&2; exit 1; }
        cp "$f" "$c/commands/"
      done
      chmod -R u+w "$c"

      # ---- Doc rewrite for the non-br parts (script calls → ecc-run + store) ----
      mds=$(find "$c/skills" "$c/commands" "$c/agents" -name '*.md')
      sed -E -i 's/(^|[^A-Za-z0-9_@.-])ecc:([a-z][a-z0-9-]*)/\1\2/g' $mds
      {
        printf '%s\n' \
          's#(python3?|node|bash) ("?)\$\{?CLAUDE_PLUGIN_ROOT\}?/#${runExe} \2${root}/#g' \
          's#(python3?|node|bash) ("?)(\$HOME|~)/\.claude/skills/#${runExe} \2${root}/skills/#g' \
          's#(python3?|node|bash) (\./)?skills/([a-z0-9-]+)/#${runExe} ${root}/skills/\3/#g' \
          's#\$\{?CLAUDE_PLUGIN_ROOT\}?/#${root}/#g' \
          's#(\$HOME|~)/\.claude/skills/([a-z0-9-]+)/(scripts|commands|hooks)/#${root}/skills/\2/\3/#g'
        for f in ${scriptGlobs}; do
          echo "s#(python3?|node|bash) (\\./)?$f\\b#${runExe} ${root}/$f#g"
        done
      } > rewrite.sed
      sed -E -i -f rewrite.sed $mds
      for d in "$c"/skills/*/; do
        skill=$(basename "$d")
        find "$d" -name '*.md' -exec sed -E -i \
          -e "s#(python3?|node|bash) (\"?)\\\$\{?SKILL_DIR\}?/#${runExe} \\2${root}/skills/$skill/#g" \
          -e "s#(python3?|node|bash) (\"?)<(skill-dir|installed-skill|native-skill-dir|docs-governance-skill)>/#${runExe} \\2${root}/skills/$skill/#g" \
          -e "s#\\\$\{?SKILL_DIR\}?/#${root}/skills/$skill/#g" \
          {} +
      done
      if [ -f "$c/commands/astra-review.md" ]; then
        sed -E -i \
          -e '/^ASTRA=""$/,/^\[ -n "\$ASTRA" \]/c\ASTRA=${root}/scripts/astra-review.js' \
          -e 's#node "\$ASTRA"#${runExe} "$ASTRA"#g' \
          "$c/commands/astra-review.md"
      fi
      sed -E -i 's/`\$\{(CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR)\}`/`\1`/g' $mds
      {
        printf '%s\n' '\$\{?CLAUDE_PLUGIN_ROOT' '\$\{?SKILL_DIR' '<skill-dir>' '\.claude/skills/[a-z0-9-]+/(scripts|commands|hooks)/' '\b(python3?|node|bash) +(\./)?skills/'
        for f in ${scriptGlobs}; do
          echo "\\b(python3?|node|bash) +(\\./)?$f\\b"
        done
      } > forbidden.re
      if grep -rnE -f forbidden.re "$c" --include='*.md' | grep -v '${runExe}' | grep -v '${root}/'; then
        echo "unwrapped ECC script invocations left in the docs" >&2
        exit 1
      fi

      # ---- Frontmatter, contract, hooks.json, self-checks ----
      python3 -I -B ${./payload-br.py} "$out" ${br} ${brHookExe}
      cp LICENSE "$out/LICENSE"
      runHook postInstall
    '';

    meta.description = "ECC payload, br flavour: orchestrator style, 23 isolated agents, path rules, br hooks";
  };
in
payload
