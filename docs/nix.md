# Nix in the harness

Each language sub-repository declares its own dev shell via `flake.nix`.
Each Apple container solution ships a flake too, providing `task` and
`just`. The host stays Nix-free; only the container needs Nix installed.

## Channel pin

Every flake pins `nixpkgs` to `nixos-25.11`. Bumping the channel is a
deliberate, per-sub-repo change.

## Where flakes live

| File | Provides |
|---|---|
| `python/flake.nix`        | python 3.13 + uv |
| `javascript/flake.nix`    | node 22 + bun + deno + JavaScript FHS wrapper for Playwright and npm-native component tooling |
| `rust/flake.nix`          | rust 1.92.0 with `wasm32-wasip1` and `llvm-tools-preview`, plus `cargo-component` and `cargo-llvm-cov` |
| `test-harness/flake.nix`  | python 3.13 + uv (runs the harness scripts) |
| `container/aarch64-darwin-apple-container-codex-universal/flake.nix` | task + just for the Codex Universal based Apple container |
| `container/aarch64-darwin-apple-container-nixos-25.11/flake.nix` | task + just for the NixOS 25.11 based Apple container |

There is no root `flake.nix` by design. The principle "language sub-repos
declare their own environment" means each sub-repo is self-contained;
the parent orchestrator discovers and invokes those contracts rather
than centralising language-specific tooling policy.

## Entering a shell

From inside the container (or any environment with Nix installed):

```sh
nix develop ./python    --command task setup
nix develop ./rust      --command task test
nix develop ./container/aarch64-darwin-apple-container-codex-universal --command bash
nix develop ./container/aarch64-darwin-apple-container-nixos-25.11 --command bash
```

## What Nix owns vs what stays as-is

| Layer | Owns |
|---|---|
| `{lang}/flake.nix` | language runtime, CLI tools, native libs |
| Language package manager (unchanged) | `uv.lock`, `package-lock.json`, `Cargo.lock` and the deps they install |
| Container | provides Nix itself; runs `nix develop` |
| Host | nothing new |

## Lockfiles

`flake.lock` files are committed per sub-repo and per container solution.
They pin nixpkgs and any extra flake inputs at that repository boundary.
Update the lockfile next to the flake whose input changed.

## Lifecycle phases

The harness defines five phases with clean boundaries. Each later phase
depends on the earlier phases having run, but is reversible without them.

| Phase | Pulls from | Network | Reversed by |
|---|---|---|---|
| `provision` | Nix install, nixpkgs, flake toolchains, Playwright browser closure | required (first run) | rebuild image |
| `setup` | PyPI, npm, crates.io (project deps via lockfiles) | required (first run) | `purge` |
| `build` | source code → wasm/transpiled artifacts | none | `clean` |
| `test` | runs build artifacts + tests | none | `clean` |
| `coverage` | runs tests + measures | none | `clean` |

**`provision` is OS-level and image-baked.** The Codex Universal
Containerfile installs Nix and pre-warms the project flakes at image build
time so `codex-harness:arm64` ships provisioned. On a fresh
`codex-universal:latest` image, `bootstrap-container-tools.sh` runs the same
logic as a runtime fallback. The NixOS 25.11 container solution starts from
`nixpkgs/nix-flakes:nixos-25.11-aarch64-linux`, where Nix is already present,
and pre-warms the same project flakes. Idempotent in both directions:
running `task provision` on an already-provisioned Codex Universal image is a
fast no-op.

**`setup` is project-level and per-checkout.** Realises lockfile state:
`uv sync`, `npm ci`, `cargo fetch`. Fast on second runs because deps
are cached locally.

**`clean` removes outputs.** `htmlcov/`, `output/`, `*.wasm`,
`transpiled/`, `bindings/`, `target/release/` etc. Anything created by
`build`, `test`, or `coverage`. Reversible by re-running them.

**`purge` removes outputs + project deps.** `clean` plus `.venv/`,
`node_modules/`, the rest of `target/`, project-local caches. Reversible
by re-running `setup`. **Does not** remove image-baked state (`/nix/store`,
Playwright browsers) — that line lives at the image
boundary; resetting it means rebuilding the image.

## Playwright is owned end-to-end by Nix

| Piece | Source |
|---|---|
| System libs (libgtk-4, libgstreamer, …) | `pkgs.playwright-driver` |
| Browser binaries (Chromium, WebKit, FFmpeg) | `pkgs.playwright-driver.browsers` |
| `playwright` npm module | `pkgs.playwright` (symlinked into `node_modules`) |
| Linux FHS runtime shape | `javascript-fhs` from `javascript/flake.nix` |

`javascript/library/package.json` does **not** declare `playwright` as a
dependency. There is one source of truth for the Playwright version:
the nixpkgs flake input. Bumping that input bumps everything in lockstep
— browsers, system libs, and the npm module — so the warm and cold
paths are bit-for-bit identical for Playwright. No `apt-get`. No
`npx playwright install`.

On Linux, WebKit is launched from inside the `PLAYWRIGHT_FHS` wrapper
exported by the JavaScript flake. JavaScript componentization uses the same
wrapper through `JCO_FHS`, because npm's `wizer` binary expects the
conventional glibc loader path. Both variables point at the Nix-built
`javascript-fhs` wrapper, keeping FHS compatibility in Nix configuration
instead of baking `/lib` loader symlinks into container images.

The trade: Playwright version follows nixpkgs's release cadence rather
than `npm install playwright@latest`. Bumping nixpkgs requires
re-running tests because Playwright's API surface may have changed.
For a contract test harness that's the right trade.

For non-Linux hosts running the JS sub-repo autonomously (e.g. a macOS
laptop), `nix develop ./javascript` provides the Linux-shaped browsers
from nixpkgs — generally fine inside any Linux container, undefined on
bare macOS. Sub-repo browser tests are container-only.

## Offline operation

After one successful `setup`, `build`/`test`/`coverage` work without
network for all three languages. The JS flake sets
`npm_config_prefer_offline=true` so npm/npx skip registry round-trips
when the cache has the answer (still fetches when missing).

## How orchestration enters Nix (Option A)

The parent `Taskfile.yml` and `justfile`'s aggregate verbs (`setup`,
`test`, `coverage`, `clean`, `purge`, `wasm:test`, `check:runners`)
wrap each per-sub-repo invocation:

```sh
cd python && nix develop --command task setup
```

Language Taskfiles/justfiles are pure: no PATH preamble, no
self-guarding, no Nix awareness. They assume the dev shell is active
and read tools from PATH normally.

Each language flake therefore declares `pkgs.go-task` and `pkgs.just`
alongside the language toolchain — so a sub-repo run autonomously
(`cd python && nix develop --command task setup`) has both the
runtime *and* the orchestrator on PATH.

The container images install or already include Nix, then pre-warm every
flake (`nix develop --command true` against each), so `/nix/store` is
populated before runtime. Ephemeral `--rm` runs hit the cache and
`nix develop` is sub-second.

## Autonomous invocation

Per the principle that sub-repos run independently of parent
orchestration, the contract for each language is:

```sh
# Inside the container (Nix is already on PATH):
cd python
nix develop --command task setup
```

That works without the parent Taskfile being involved. Outside the
container, the requirement is having Nix installed; otherwise the same
command works.

## Status

Done:

- Per-sub-repo `flake.nix` + `flake.lock` exist and provide the toolchains
  above. Locks pin nixpkgs to `nixos-25.11 @ a4bf066`.
- Each language flake also provides `pkgs.go-task` and `pkgs.just` so
  the sub-repo's lifecycle runs without the parent.
- Codex Universal Apple container solution lives under
  `container/aarch64-darwin-apple-container-codex-universal/`.
- NixOS 25.11 Apple container solution lives under
  `container/aarch64-darwin-apple-container-nixos-25.11/`.
- Container images install or already include Nix and pre-warm every flake at
  build time.
- `bootstrap-container-tools.sh` is now a 30-line fallback that installs
  Nix on a fresh codex-universal image (used when running the base image
  directly without the harness's image build).
- Parent Taskfile and justfile aggregates wrap per-language calls in
  `nix develop`. `task wasm:test` and `task check:runners` go through
  `nix develop ./test-harness`.
- All language Taskfiles/justfiles have their PATH preambles removed.
  The rust Taskfiles no longer self-install cargo-component or
  cargo-llvm-cov; the flake provides them.
- `cargo-llvm-cov` aligned to `0.6.20` (what nixpkgs 25.11 ships).
- Lifecycle phases (`provision`, `setup`, `build`, `test`, `coverage`,
  `clean`, `purge`) are separated by source of state; `task provision`
  exposes the bootstrap script as a discoverable verb.
- JavaScript browser tests run WebKit through the Nix-provided FHS wrapper,
  so the Linux browser matrix no longer needs apt or `PLAYWRIGHT_SKIP_WEBKIT`.
- JavaScript componentization runs `jco` through the same FHS wrapper via
  `JCO_FHS`, so npm-native Linux binaries do not require image-baked loader
  symlinks.
- `npx playwright install` is not part of setup or provision. Setup is
  `npm ci` plus the Nix-store Playwright symlink.

## Playwright on Linux

Plain `nix develop ./javascript` exposes `pkgs.playwright` and
`pkgs.playwright-driver.browsers`, but WPE WebKit needs an FHS-shaped
runtime for graphics and media libraries loaded outside the direct ELF
closure. The flake exports `PLAYWRIGHT_FHS`; JavaScript library test
commands use it for Node browser tests. Chromium and WebKit both run from
the nixpkgs browser bundle.

## JavaScript componentization on Linux

`jco componentize` shells out to npm-provided native binaries, including
`@bytecodealliance/wizer-linux-arm64/wizer` on Apple-silicon Linux
containers. That binary expects `/lib/ld-linux-aarch64.so.1`, which a
NixOS-style filesystem does not provide by default. The JavaScript flake
therefore exports `JCO_FHS` pointing at the same `javascript-fhs` wrapper
used by Playwright. The component Taskfile and justfile run `jco componentize`
and `jco transpile` through that wrapper when it is available.
