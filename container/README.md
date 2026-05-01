# Apple Container Solutions

This directory contains separate Apple `container` solutions. Each solution has
its own scripts, `Containerfile`, flake, and README so the behavior is explicit
instead of controlled by option switches.

## Solutions

| Directory | Host | Guest/base image | Default image tag |
|---|---|---|---|
| `aarch64-darwin-apple-container-codex-universal/` | Apple silicon macOS | `ghcr.io/openai/codex-universal:latest` | `codex-harness:arm64` |
| `aarch64-darwin-apple-container-nixos-25.11/` | Apple silicon macOS | `nixpkgs/nix-flakes:nixos-25.11-aarch64-linux` | `codex-harness:arm64-nixos` |

Use the root `task` or `just` commands for normal operation. The `container:*`
commands target the Codex Universal based solution; the `container:nixos:*`
commands target the NixOS 25.11 based solution.

```sh
task container:build
task container:test

task container:nixos:build
task container:nixos:test
```

For no-bind validation of a source-containing image, use the `host:container:*`
or `host:container:nixos:*` commands after building the corresponding image.
