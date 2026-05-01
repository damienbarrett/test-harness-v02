{
  description = "NixOS Apple container guest shell";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" "x86_64-darwin" ];
      forSystems = f: nixpkgs.lib.genAttrs systems
        (system: f nixpkgs.legacyPackages.${system});
    in {
      devShells = forSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [
            pkgs.bashInteractive
            pkgs.coreutils
            pkgs.gawk
            pkgs.gnugrep
            pkgs.gnused
            pkgs.go-task
            pkgs.just
          ];
        };
      });
    };
}
