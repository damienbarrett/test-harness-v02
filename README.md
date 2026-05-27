# Getting started

Clone the project:

```bash
git clone https://github.com/damienbarrett/test-harness-v02
```

This is a monorepo. `common/`, `python/`, `javascript/`, `rust/`, and
`test-harness/` are normal tracked directories.

## Sparse worktrees

Use sparse worktrees for agent sessions that should only see part of the
monorepo:

```bash
bin/dx-worktree create rust-bindgen rust
cd .worktrees/rust-bindgen
```

Every sparse worktree includes root-level files, `bin/`, and `common/`.
Additional command arguments select the workstream-specific directories.

Sparse-checkout only controls which files are present in that worktree. It does
not prevent a process from leaving the worktree if the surrounding execution
harness allows it. See `docs/worktrees.md` for details.

## Lifecycle

Repositories that participate in the lifecycle expose:

```bash
task setup
task test
task coverage
task clean
task purge
```

`clean` removes generated outputs while preserving dependency/setup state. `purge` removes generated outputs and repo-owned setup artifacts, so the next `setup` may be slower.

Ignored workspace state is organized under `.harness/` by the lifecycle stage that removes it:

```text
.harness/
  outputs/  # removed by clean and purge
  cache/    # removed by purge
```

Lifecycle state names should describe the lifecycle step that owns removal. Build and report artifacts belong under `outputs`; dependency and setup reuse state belongs under `cache`.

Python and test-harness lifecycle commands use `.harness/cache` by default instead of the host-global uv cache under the user's home directory. Override with `HARNESS_DIR=/path/to/state` or `UV_CACHE_DIR=/path/to/cache` when needed.

`common/` is a source-contract repository for shared schemas, WIT, and fixtures. It is consumed by lifecycle repositories but does not expose lifecycle commands.
