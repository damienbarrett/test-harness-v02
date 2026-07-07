# 0004. Task/Just Parity Strategy

Date: 2026-07-07

Status: accepted

## Context

Constitution.md §4 requires "every layer exposes the exact same verbs"
regardless of which lightweight runner (Task or Just) is used, and the
refactoring plan lists "lifecycle commands remain reproducible and work
through both Task and Just" as an invariant that must never regress. The two
runners had drifted in practice: the Phase 0 baseline recorded 71
command-body mismatches between `Taskfile.yml`/`justfile` pairs, and those
mismatches were only warnings, not failures, so nothing stopped the drift
from growing.

## Decision

Every directory with real command-body content gets one canonical,
self-contained `lifecycle.sh <verb>` script. That directory's `Taskfile.yml`
and `justfile` recipes both reduce to the identical one-line body
`./lifecycle.sh <verb>`; the only tolerated normalization is how each DSL
spells "the rest of the CLI arguments" (`{{.CLI_ARGS}}` in Task versus a
variadic parameter reference in Just), which
`test-harness/src/harness/runner_parity.py` folds to one canonical token
before comparing. Pure aggregator recipes (which only depend on other
recipes and have no literal shell work of their own) keep each runner's
native dependency-graph syntax instead of delegating to a script, since that
already matches byte-for-byte and preserves Task's `sources:`/`generates:`
incremental-skip hints. `runner_parity.py` (wired into `check:runners` /
`check-runners`) walks every pair and fails -- not warns -- on any
recipe-name, dependency, or normalized-command-body mismatch, and
`test-harness/tests/test_runner_behavioral_parity.py` additionally executes
both real `task` and `just` binaries against a temporary fixture project to
assert equivalent commands, environment variables, working directories,
dependencies, cleanup paths, and failure propagation.

## Consequences

- A behavioral change to a directory's lifecycle only needs to be made in
  one place (`lifecycle.sh`); both runners inherit it automatically and
  cannot silently diverge.
- `check:runners` now genuinely blocks a drifted change instead of printing
  a warning that can be ignored -- the historical 71-then-74-warning backlog
  is 0 by construction, not by cleanup effort alone.
- Recipe names and dependency graphs are still declared natively per runner
  (for CLI discoverability and Task's incremental-build behavior), so the
  parity checker has to compare those separately from command bodies rather
  than diffing one shared manifest.
- Adding a new lifecycle verb to any directory means writing it once in
  `lifecycle.sh` and adding one matching one-line recipe to each runner file;
  forgetting either file is caught by `check:runners` in CI, not by review
  vigilance.
