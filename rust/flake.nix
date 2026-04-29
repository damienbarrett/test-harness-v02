{
  description = "Rust sub-repo dev shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, rust-overlay }:
    let
      systems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" "x86_64-darwin" ];
      forSystems = f: nixpkgs.lib.genAttrs systems (system:
        f (import nixpkgs {
          inherit system;
          overlays = [ rust-overlay.overlays.default ];
        }));
    in {
      devShells = forSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [
            (pkgs.rust-bin.stable."1.92.0".default.override {
              targets = [ "wasm32-wasip1" ];
              extensions = [ "llvm-tools-preview" ];
            })
            pkgs.cargo-component
            pkgs.cargo-llvm-cov
            pkgs.go-task
            pkgs.just
          ];
        };
      });
    };
}
