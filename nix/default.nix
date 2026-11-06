# mk { pkgs } -> { payload hook python }. One call yields the same derivations for every consumer.
{ pkgs }:
let
  # Stdlib only: validate.py, hooks and tests need no third-party packages.
  python = pkgs.python3;
  hook = pkgs.callPackage ./hook.nix { inherit python; };
  payload = pkgs.callPackage ./payload.nix {
    inherit python;
    brHook = hook;
  };
in
{
  inherit payload hook python;
}
