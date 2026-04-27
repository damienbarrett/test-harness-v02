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

Python and test-harness lifecycle commands use a gitignored repo-local uv cache by default instead of the host-global cache under the user's home directory. Override with `UV_CACHE_DIR=/path/to/cache` when needed.

`common/` is a source-contract repository for shared schemas, WIT, and fixtures. It is consumed by lifecycle repositories but does not expose lifecycle commands.
