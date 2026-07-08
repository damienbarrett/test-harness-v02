{
  description = "Test-harness sub-repo dev shell — runs the harness scripts";

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
            pkgs.python313
            pkgs.uv
            pkgs.go-task
            pkgs.just
            # ruff, shellcheck (constitution.md §8): both
            # provided by nixpkgs rather than as uv-managed project
            # dependencies/ad-hoc downloads. See python/flake.nix for why
            # ruff specifically must come from Nix in this guest OS (no FHS
            # loader for prebuilt native wheels). shellcheck has no uv/npm
            # equivalent home in this repo at all - it backs the `check-shell`
            # verb that scans every tracked shell script repo-wide.
            pkgs.ruff
            pkgs.shellcheck
          ];
        };
      });
    };
}
