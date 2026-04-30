{
  description = "JavaScript sub-repo dev shell";

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
            pkgs.nodejs_22
            pkgs.bun
            pkgs.deno
            pkgs.go-task
            pkgs.just
            # Playwright is owned end-to-end by Nix: the npm module
            # symlinked into node_modules by `task setup`, browsers +
            # system libs from the driver. `playwright` is intentionally
            # absent from package.json — one source of truth for the
            # Playwright version is nixpkgs.
            pkgs.playwright
            pkgs.playwright-driver
          ];
          shellHook = ''
            # `pkgs.playwright` packages playwright-core: its store root
            # is the npm package root (package.json + index.mjs etc.).
            # Node's ESM resolution ignores NODE_PATH so `task setup`
            # symlinks node_modules/playwright -> $PLAYWRIGHT_NPM_PATH.
            export PLAYWRIGHT_NPM_PATH=${pkgs.playwright}
            export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
            export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
            # nixpkgs's playwright-driver ships WPE WebKit, which
            # requires hardware EGL. Apple's container has no GPU;
            # MiniBrowser-wpe aborts at startup with "Could not create
            # WPE EGL display". Skip WebKit until WebKitGTK with Xvfb
            # is wired up; Chromium covers the contract test.
            export PLAYWRIGHT_SKIP_WEBKIT=1
            # npm/npx make registry round-trips on every invocation
            # even when packages are locally installed. prefer-offline
            # tells them to skip those round-trips when the cache has
            # the answer, while still fetching when it's missing.
            export npm_config_prefer_offline=true
          '';
        };
      });
    };
}
