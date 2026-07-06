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
        # `minimal` (rustc, cargo, rust-std only) instead of `default`
        # (adds rust-docs, rustfmt, clippy) plus only the extensions this
        # repo actually needs (docs/refactoring-plan.md Phase 8):
        #   - llvm-tools-preview: required by cargo-llvm-cov (`task
        #     rust-coverage`) for source-based coverage instrumentation.
        #   - clippy, rustfmt: not used by any lifecycle verb yet, but
        #     Phase 9's quality gates (`cargo fmt --check`, `cargo clippy
        #     -D warnings`) will need them, so they are kept explicit
        #     extensions here rather than pulled in incidentally via
        #     `default`. rust-analyzer and rust-docs are not needed by any
        #     lifecycle verb or editor tooling this repo depends on, so
        #     they are dropped.
        default = pkgs.mkShell {
          packages = [
            (pkgs.rust-bin.stable."1.92.0".minimal.override {
              targets = [ "wasm32-wasip1" ];
              extensions = [ "llvm-tools-preview" "clippy" "rustfmt" ];
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
