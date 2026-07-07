# 0005. Separate Container Implementations

Date: 2026-07-07

Status: accepted

## Context

Constitution.md §1 requires results to be identical "regardless of whether
they run on an M1 Mac, a Raspberry Pi, or an AI Cloud environment," and §2
assigns the container layer responsibility for protecting the host from
filesystem drift. Two Apple `container` base images are both viable for this
repository: a Codex-universal-based image (the original solution, which
installs Nix at runtime as a fallback) and a NixOS 25.11 based image (which
already ships Nix). The refactoring plan lists "combining the two Apple
container implementations" as explicitly out of scope unless separately
approved, and Phase 10 reaffirmed keeping them separate rather than merging
their logic.

## Decision

`container/aarch64-darwin-apple-container-codex-universal/` and
`container/aarch64-darwin-apple-container-nixos-25.11/` remain two complete,
independent solutions, each with its own `Containerfile`,
`flake.nix`/`flake.lock`, and full set of `container-*.sh` scripts
(build/pull/run/shell/healthcheck/suite/prune-all), rather than a single
script parameterized by base-image mode -- matching the original
implementation rule to "prefer duplicated, easy-to-read scripts over clever
shared logic" and to never make one script switch between base images. Root
Task/Just expose both solutions under separate command namespaces
(`container:*` for Codex Universal, `container:nixos:*` for NixOS), and both
route through the shared `container-suite.sh` fail-fast policy (constitution
§4: "the orchestrator exits non-zero immediately," no silent partial
successes, with an explicit `--diagnostic` / `CONTAINER_SUITE_DIAGNOSTIC=1`
opt-in for a failure-collecting run) -- a policy that Phase 10 had to change
independently in each solution's own script rather than through shared code.

## Consequences

- The two solutions duplicate a meaningful amount of script and
  `Containerfile` logic; that duplication is an accepted, deliberate cost of
  keeping each base image's behavior explicit and independently auditable.
- A fix to one container solution's scripts does not automatically apply to
  the other -- the Phase 10 fail-fast policy change had to be made twice,
  and any future fix carries the same cost.
- The byte-identity of the two solutions' `container-suite.sh` policy
  scripts is now pinned by a harness test
  (`test-harness/tests/test_container_policy_sync.py`); a deliberate
  divergence must update that test and this ADR.
- Extracting shared, base-image-neutral low-level operations remains an
  option a maintainer could approve later (Phase 10 left it "N/A -- not
  approved"), but this ADR does not block that -- provided the public entry
  scripts for each solution stay separate.
- Both solutions must expose the same root-level command surface
  (`task container:*` / `task container:nixos:*` and their Just
  equivalents) so a caller does not need to know which base image is active
  to run `setup`/`test`/`coverage`/`clean`/`purge`.
