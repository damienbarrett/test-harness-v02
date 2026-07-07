# aarch64-darwin Apple Container, NixOS 25.11 Guest

This solution runs the harness with Apple's `container` CLI on an
Apple-silicon macOS host and a Nix/NixOS 25.11 guest image.

The base image is:

```text
nixpkgs/nix-flakes:nixos-25.11-aarch64-linux
```

Nix is already present in the base image, so this solution does not install
Nix at runtime. The `Containerfile` pre-warms the same project flakes as the
Codex Universal solution and copies the repository to `/workspace/v02` for
image-mode runs.

This is a process container image, not a full systemd-booted NixOS runtime.
The NixOS/Nixpkgs base provides a Linux filesystem with Nix and the pinned
Nixpkgs channel; project commands still run through `nix develop`.

JavaScript browser tests and JavaScript componentization use the
`javascript-fhs` wrapper exported by `javascript/flake.nix`. That keeps the
FHS-shaped runtime in Nix configuration instead of baking loader symlinks into
this image.

Common commands from the repository root:

```sh
task container:nixos:pull
task container:nixos:build
task container:nixos:test
task container:nixos:coverage
```

No-bind validation against the source-containing image is available through:

```sh
task host:container:nixos:test
task host:container:nixos:coverage
```

The scripts also support bind-mounted iteration directly:

```sh
./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh \
  './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both test'
```

Validation status: the rebuilt `codex-harness:arm64-nixos` image passes
`both test` and `both coverage` in image workspace mode.

## Container suite failure policy

`container-suite.sh` is fail-fast by default, per `constitution.md` §4: the
first failing step (`setup`, `test`, `coverage`, `clean`, or `purge`, and for
`both` scope the first failing runner) stops the run immediately with a
non-zero exit and a message naming the step. A failed `setup` is never
followed by `test`/`coverage`.

Pass `--diagnostic`, or set `CONTAINER_SUITE_DIAGNOSTIC=1`, to opt into
running every remaining step anyway (e.g. to see whether `test` also fails
after a broken `setup`). Diagnostic runs are clearly labelled `DIAGNOSTIC
MODE` in their output and still exit non-zero if anything failed.
