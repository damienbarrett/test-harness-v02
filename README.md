# Getting started

Clone the project with all submodules:

```bash
git clone --recurse-submodules https://github.com/damienbarrett/test-harness-v02
```

If already cloned without submodules:

```bash
git submodule update --init
```

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
