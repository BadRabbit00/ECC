{
  description = "br: orchestrator output style and isolated subagents for Claude Code, packaged for Nix";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      # For consumers with their own nixpkgs: br.lib.mk { inherit pkgs; } -> { payload hook python }.
      lib.mk = { pkgs, ... }: import ./nix { inherit pkgs; };

      packages = forAll (
        pkgs:
        let
          br = self.lib.mk { inherit pkgs; };
        in
        {
          default = br.payload;
          br-payload = br.payload;
          br-hook = br.hook;
        }
      );

      # The validator and all Python tests run in the payload checkPhase: a red test is a red build.
      checks = forAll (pkgs: {
        inherit (self.lib.mk { inherit pkgs; }) payload;
      });

      devShells = forAll (
        pkgs:
        let
          br = self.lib.mk { inherit pkgs; };
        in
        {
          default = pkgs.mkShell {
            packages = [
              br.python
              pkgs.git
              pkgs.nixfmt
              pkgs.statix
              pkgs.deadnix
            ];
          };
        }
      );

      formatter = forAll (pkgs: pkgs.nixfmt);
    };
}
