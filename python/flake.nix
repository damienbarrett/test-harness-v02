{
  description = "Python sub-repo dev shell";

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
            # ruff (Phase 9 of docs/refactoring-plan.md): provided by nixpkgs
            # rather than as a uv-managed project dependency. Ruff ships as a
            # prebuilt native (Rust) binary; the NixOS-based guest OS this
            # repo standardizes on has no FHS `/lib/ld-linux*` loader path
            # (by design - see javascript/flake.nix's FHS shim, needed for
            # the same underlying reason), so a `uv`/pip-installed manylinux
            # wheel cannot execute here, only nixpkgs' own patched build can.
            # This mirrors how rust/flake.nix already provides clippy and
            # rustfmt as Nix toolchain extensions rather than Cargo
            # dependencies.
            pkgs.ruff
          ];
        };
      });
    };
}
