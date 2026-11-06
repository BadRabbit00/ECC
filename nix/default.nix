# mk { pkgs } -> { payload hook python }. Один вызов — одна и та же деривация для всех потребителей.
{ pkgs }:
let
  # Только stdlib: validate.py, хуки и тесты не тянут сторонних пакетов.
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
