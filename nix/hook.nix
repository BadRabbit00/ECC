# br-hook <entry>: br hooks (hooks/*.py, stdlib only). Pinned python, scripts run from their own
# store path without tests: editing tests does not rebuild the hook.
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
  # git: the guards read the current branch.
  runtimeInputs = [
    python
    git
  ];
  # Exit codes: 2 = wiring error (bad or missing entry), fail-CLOSED: a guard that silently
  # disappears is worse than a visibly blocked tool call. Runtime crashes inside a hook exit 1
  # and stay fail-open (the tool call proceeds), by design.
  text = ''
    entry=''${1:?usage: br-hook <entry>}
    if [[ ! "$entry" =~ ^(guard|check|fix)_[a-z_]+$ ]] || [ ! -f ${hooks}/"$entry".py ]; then
      echo "br-hook: unknown entry $entry" >&2
      exit 2
    fi
    # -I: no PYTHONPATH or user site; -B: the store is read-only.
    exec python3 -I -B ${hooks}/"$entry".py
  '';
  meta = {
    description = "Runs a br hook entry (guard_*, check_*, fix_*) with a pinned python";
    license = lib.licenses.mit;
  };
}
