# Nix in the harness

Each language sub-repository declares its own dev shell via `flake.nix`.
The container layer ships a flake too, providing `task` and `just`. The
host stays Nix-free; only the container needs Nix installed.

## Channel pin

Every flake pins `nixpkgs` to `nixos-25.11`. Bumping the channel is a
deliberate, per-sub-repo change.

## Where flakes live

| File | Provides |
|---|---|
| `python/flake.nix`        | python 3.13 + uv |
| `javascript/flake.nix`    | node 22 + bun + deno |
| `rust/flake.nix`          | rust 1.92.0 with `wasm32-wasip1` and `llvm-tools-preview`, plus `cargo-component` and `cargo-llvm-cov` |
| `test-harness/flake.nix`  | python 3.13 + uv (runs the harness scripts) |
| `container/flake.nix`     | task + just |

There is no root `flake.nix` by design. The principle "language sub-repos
declare their own environment" means each sub-repo is self-contained;
the parent orchestrator discovers and invokes those contracts rather
than centralising language-specific tooling policy.

## Entering a shell

From inside the container (or any environment with Nix installed):

```sh
nix develop ./python    --command task setup
nix develop ./rust      --command task test
nix develop ./container --command bash
```

## What Nix owns vs what stays as-is

| Layer | Owns |
|---|---|
| `{lang}/flake.nix` | language runtime, CLI tools, native libs |
| Language package manager (unchanged) | `uv.lock`, `package-lock.json`, `Cargo.lock` and the deps they install |
| Container | provides Nix itself; runs `nix develop` |
| Host | nothing new |

## Lockfiles

`flake.lock` files are not committed yet. They are generated on first
`nix develop` and should be committed once produced inside the container.
Until they are, each flake floats on the tip of the `nixos-25.11`
nixpkgs branch.

## Status — what's done, what's next

Done in this change:

- Per-sub-repo `flake.nix` files exist and provide the toolchains above.
- `container/flake.nix` provides task + just.

Deferred (separate change):

- Replace the imperative `cargo install` / `go install` / `rustup` blocks
  in `container/Containerfile` and `container/bootstrap-container-tools.sh`
  with a Nix install + `nix develop` entry. Doing this requires rewiring
  the existing `image-*` / `container-*` orchestration so that direct
  invocation outside Nix does not regress.
- Remove the `~/.local/bin:~/.cargo/bin:~/go/bin` PATH preamble from every
  Taskfile/justfile. The Nix shell sets PATH correctly, so the preamble
  becomes redundant — but only once all entry points go through
  `nix develop`.

## Playwright on Linux — known gotcha

`javascript/library/setup` calls `npx playwright install --with-deps` on
Linux, which expects `apt-get`. Inside a Nix-only environment this will
fail. If/when the base image becomes Nix-native, switch to
`pkgs.playwright-driver` and set `PLAYWRIGHT_BROWSERS_PATH` from the
flake. Today the apt-based base image keeps this working, so no change
is required yet.
