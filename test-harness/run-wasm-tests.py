#!/bin/sh
# Thin shim: delegates to the locked `harness` project so dependency
# resolution goes through `uv.lock` instead of an ad-hoc `--with` script
# manifest. See src/harness/cli.py for the actual implementation.
exec uv run --locked --project "$(dirname "$0")" python -m harness.cli "$@"
