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

## Lifecycle phases

The harness defines five phases with clean boundaries. Each later phase
depends on the earlier phases having run, but is reversible without them.

| Phase | Pulls from | Network | Reversed by |
|---|---|---|---|
| `provision` | Nix install, nixpkgs, flake toolchains, apt system libs, Playwright browsers | required (first run) | rebuild image |
| `setup` | PyPI, npm, crates.io (project deps via lockfiles) | required (first run) | `purge` |
| `build` | source code → wasm/transpiled artifacts | none | `clean` |
| `test` | runs build artifacts + tests | none | `clean` |
| `coverage` | runs tests + measures | none | `clean` |

**`provision` is OS-level and image-baked.** The Containerfile runs the
equivalent of `task provision` at image build time so
`codex-harness:arm64-nix` ships fully provisioned. On a fresh
`codex-universal:latest` image, `bootstrap-container-tools.sh` runs the
same logic as a runtime fallback. Idempotent in both directions —
running `task provision` on an already-provisioned image is a fast no-op.

**`setup` is project-level and per-checkout.** Realises lockfile state:
`uv sync`, `npm ci`, `cargo fetch`. Fast on second runs because deps
are cached locally.

**`clean` removes outputs.** `htmlcov/`, `output/`, `*.wasm`,
`transpiled/`, `bindings/`, `target/release/` etc. Anything created by
`build`, `test`, or `coverage`. Reversible by re-running them.

**`purge` removes outputs + project deps.** `clean` plus `.venv/`,
`node_modules/`, the rest of `target/`, project-local caches. Reversible
by re-running `setup`. **Does not** remove image-baked state (`/nix/store`,
apt packages, Playwright browsers) — that line lives at the image
boundary; resetting it means rebuilding the image.

## Why Playwright lives in `provision`, not `setup`

Playwright's runtime needs are split between two upstream-prebuilt artifacts:

| Piece | Source | Phase |
|---|---|---|
| System libs (libgtk-4, libgstreamer, …) | Ubuntu apt | `provision` |
| Browser binaries (Chromium, WebKit, FFmpeg) | playwright.dev CDN | `provision` |
| `playwright` npm package | npmjs registry | `setup` |

System libs are OS-version-specific and `apt-get` requires sudo + a
working apt repo — both of which work cleanly outside `nix develop` but
get tangled inside it. Browser binaries are prebuilt and could go in
either phase; placing them in `provision` keeps the image-bake/runtime
fallback symmetry simple.

The `playwright` *package* itself stays in `setup` (it's just an npm
dep). What `setup` no longer does is `npx playwright install`.

For non-Linux hosts running the JS sub-repo autonomously (e.g. a macOS
laptop without the container), `setup` still installs browsers locally
because there's no `provision` step that would do it.

## Offline operation

After `provision` and one successful `setup`, `build`/`test`/`coverage`
work without network for Python and Rust. JavaScript needs one extra
flag because `npm ci` and `npx` make opportunistic registry round-trips
even when packages are locally installed. Set `npm_config_offline=true`
to suppress them.

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

The container image installs Nix at build time and pre-warms every
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
- Container image installs Nix and pre-warms every flake at build time.
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
- `npx playwright install` moved out of `javascript/library/setup` into
  `provision`. Setup is now `npm ci` only on Linux.

## Playwright on Linux — known gotcha

`javascript/library/setup` calls `npx playwright install --with-deps` on
Linux, which expects `apt-get`. Inside a Nix-only environment this will
fail. If/when the base image becomes Nix-native, switch to
`pkgs.playwright-driver` and set `PLAYWRIGHT_BROWSERS_PATH` from the
flake. Today the apt-based base image keeps this working, so no change
is required yet.
