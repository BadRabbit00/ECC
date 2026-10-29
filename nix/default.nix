# Nix-упаковка этого форка ECC: дерево в сторе + обёртки (runtime.nix) и
# выборка/переписанная документация для трёх CLI (payload.nix).
# Потребитель — Home Manager в BadRabbit00/nixos-conf (home/ai/ecc/default.nix),
# который раскладывает payload по ~/.claude, ~/.codex и ~/.gemini/config и
# вливает hooks.json в settings.json. Здесь только чистые деривации.
{ pkgs, lib ? pkgs.lib, src, version }:

let
  runtime = import ./runtime.nix { inherit lib pkgs src version; };
  payload = import ./payload.nix { inherit lib pkgs runtime; };
in
{
  inherit runtime payload;
  inherit (runtime) root run hook;
}
