#!/bin/sh
# Thin shim: delegates to the locked `harness` project so dependency
# resolution goes through `uv.lock` instead of an ad-hoc `--with` script
# manifest. See src/harness/runner_parity.py for the actual implementation.
exec uv run --locked --project "$(dirname "$0")" python -m harness.runner_parity "$@"
