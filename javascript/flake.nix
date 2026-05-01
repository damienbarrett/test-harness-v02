{
  description = "JavaScript sub-repo dev shell";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" "x86_64-darwin" ];
      forSystems = f: nixpkgs.lib.genAttrs systems
        (system: f nixpkgs.legacyPackages.${system});
      playwrightFhs = pkgs:
        pkgs.buildFHSEnv (
          pkgs.appimageTools.defaultFhsEnvArgs
          // {
            name = "javascript-playwright-fhs";

            targetPkgs = innerPkgs:
              (pkgs.appimageTools.defaultFhsEnvArgs.targetPkgs innerPkgs)
              ++ (with innerPkgs; [
                nodejs_22
                bun
                deno
                go-task
                just
                playwright
                playwright-driver
                playwright-driver.browsers
                glibcLocales
                tzdata

                at-spi2-atk
                brotli
                cairo
                cups
                dbus
                expat
                flite
                fontconfig
                freetype
                glib
                glib-networking
                gst_all_1.gst-libav
                gst_all_1.gst-plugins-bad
                gst_all_1.gst-plugins-base
                gst_all_1.gst-plugins-good
                gst_all_1.gstreamer
                gtk3
                harfbuzzFull
                hyphen
                icu74
                lcms
                libavif
                libdrm
                libepoxy
                libevent
                libgbm
                libgcc.lib
                libgcrypt
                libglvnd
                libgpg-error
                libjpeg8
                libjxl
                libopus
                libpng
                libpsl
                libsoup_3
                libtasn1
                libvpx
                libwebp
                libwpe
                libwpe-fdo
                libxkbcommon
                (pkgs.lib.getLib libxml2_13)
                (pkgs.lib.getLib libxml2)
                libxslt
                mesa
                nghttp2
                nspr
                nss
                pango
                sqlite
                systemdLibs
                wayland
                wayland-scanner
                woff2
                xorg.libX11
                xorg.libXScrnSaver
                xorg.libXcomposite
                xorg.libXcursor
                xorg.libXdamage
                xorg.libXext
                xorg.libXfixes
                xorg.libXi
                xorg.libXrandr
                xorg.libXtst
                xorg.libxcb
                zlib
              ]);

            profile = ''
              export LANG=C.UTF-8
              export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
              export npm_config_prefer_offline=true
            '';

            runScript = "bash";
          }
        );
    in {
      devShells = forSystems (pkgs: {
        default =
          let
            fhs = if pkgs.stdenv.isLinux then playwrightFhs pkgs else null;
          in
          pkgs.mkShell {
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
            ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [ fhs ];
            shellHook = ''
              # `pkgs.playwright` packages playwright-core: its store root
              # is the npm package root (package.json + index.mjs etc.).
              # Node's ESM resolution ignores NODE_PATH so `task setup`
              # symlinks node_modules/playwright -> $PLAYWRIGHT_NPM_PATH.
              export PLAYWRIGHT_NPM_PATH=${pkgs.playwright}
              export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
              export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
              ${if pkgs.stdenv.isLinux then ''
                # WPE WebKit needs an FHS-shaped runtime for dlopen'd graphics
                # and media libraries. The browser binaries and Playwright npm
                # module still come from nixpkgs.
                export PLAYWRIGHT_FHS=${fhs}/bin/javascript-playwright-fhs
              '' else ''
                export PLAYWRIGHT_SKIP_WEBKIT=1
              ''}
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
