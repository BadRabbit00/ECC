{
  description = "BadRabbit fork of ECC (Everything Claude Code): upstream + own skills, packaged for Nix";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      # 2.2.3 — версия апстрима, дата — последний коммит этого дерева.
      date = self.lastModifiedDate or "19700101";
      version = "2.2.3-unstable-${builtins.substring 0 4 date}-${builtins.substring 4 2 date}-${builtins.substring 6 2 date}";
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
        });

      # Разработка форка: валидаторы апстрима и тесты гоняются тем же node, что
      # в обёртках; node_modules — симлинк в тот же стор-путь, что у рантайма.
      devShells = forAll (pkgs:
        let ecc = self.lib.mk { inherit pkgs; };
        in {
          default = pkgs.mkShell {
            packages = [ pkgs.nodejs ecc.runtime.python pkgs.jq pkgs.gawk pkgs.remarshal pkgs.git ];
            shellHook = ''
              ln -sfn ${ecc.runtime.nodeModules}/node_modules node_modules
              echo "ecc devShell: node $(node --version); validators: node scripts/ci/validate-*.js; tests: node tests/run-all.js tests/ci" >&2
            '';
          };
        });

      checks = forAll (pkgs: {
        payload = (self.lib.mk { inherit pkgs; }).payload;
      });
    };
}
