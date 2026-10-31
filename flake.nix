{
  description = "BadRabbit fork of ECC (Everything Claude Code): upstream + own skills, packaged for Nix";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      # Версия апстрима из package.json, дата — последний коммит этого дерева.
      upstream = (builtins.fromJSON (builtins.readFile ./package.json)).version;
      date = self.lastModifiedDate or "19700101";
      version = "${upstream}-unstable-${builtins.substring 0 4 date}-${builtins.substring 4 2 date}-${builtins.substring 6 2 date}";
    in
    {
      # Для потребителей с собственным nixpkgs: ecc.lib.mk { inherit pkgs; }
      # -> { runtime payload root run hook }. Один и тот же вызов — одна деривация.
      lib.mk = { pkgs, lib ? pkgs.lib }: import ./nix { inherit pkgs lib version; src = self; };

      packages = forAll (pkgs:
        let ecc = self.lib.mk { inherit pkgs; };
        in {
          default = ecc.payload;
          ecc = ecc.root;          # репозиторий + node_modules в сторе (с тестами хуков)
          ecc-run = ecc.run;
          ecc-hook = ecc.hook;
          ecc-payload = ecc.payload;
          ecc-payload-br = ecc.payloadBr;   # flavour br (badrabbit/): ecc.flavour = "br" in nixos-conf
          br-hook = ecc.brHook;
        });

      # Разработка форка: валидаторы апстрима и тесты гоняются тем же node, что
      # в обёртках; node_modules — симлинк в тот же стор-путь, что у рантайма.
      devShells = forAll (pkgs:
        let ecc = self.lib.mk { inherit pkgs; };
        in {
          default = pkgs.mkShell {
            packages = [ pkgs.nodejs ecc.runtime.python pkgs.jq pkgs.gawk pkgs.remarshal pkgs.git ];
            shellHook = ''
              # node_modules — симлинк в корне репозитория (а не в текущем каталоге),
              # и только если там не лежит настоящий каталог после npm ci.
              top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
              if [ ! -e "$top/node_modules" ] || [ -L "$top/node_modules" ]; then
                ln -sfn ${ecc.runtime.nodeModules}/node_modules "$top/node_modules"
              fi
              echo "ecc devShell: node $(node --version); validators: node scripts/ci/validate-*.js; tests: node tests/run-all.js tests/ci" >&2
            '';
          };
        });

      checks = forAll (pkgs: let ecc = self.lib.mk { inherit pkgs; }; in {
        inherit (ecc) payload;
        payload-br = ecc.payloadBr;   # runs the br validator and test suites in checkPhase
      });
    };
}
