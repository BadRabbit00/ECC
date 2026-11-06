# br-hook <entry>: хуки br (hooks/*.py, только stdlib). Запиненный python, скрипты из своего
# store-пути без тестов: правка тестов не пересобирает хук.
{
  lib,
  writeShellApplication,
  git,
  python,
}:
let
  hooks = lib.fileset.toSource {
    root = ../hooks;
    fileset = lib.fileset.difference ../hooks (
      lib.fileset.unions [
        ../hooks/test
        ../hooks/README.md
        ../hooks/hooks.json
      ]
    );
  };
in
writeShellApplication {
  name = "br-hook";
  # git: guard-ы читают текущую ветку.
  runtimeInputs = [
    python
    git
  ];
  text = ''
    entry=''${1:?usage: br-hook <entry>}
    case "$entry" in
      guard_*|check_*|fix_*) ;;
      *) echo "br-hook: unknown entry $entry" >&2; exit 64 ;;
    esac
    # -I: без PYTHONPATH и user site; -B: стор только для чтения.
    exec python3 -I -B ${hooks}/"$entry".py
  '';
  meta.mainProgram = "br-hook";
}
