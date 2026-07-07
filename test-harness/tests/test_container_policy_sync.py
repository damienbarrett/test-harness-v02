"""Guard against accidental drift between the two container-suite policies.

ADR 0005 keeps the two Apple ``container`` solutions as complete, separate
implementations, and Phase 10 applied the same fail-fast suite policy to
each one independently. The two resulting ``container-suite.sh`` scripts are
byte-identical BY INTENT -- this test pins that identity so an edit to one
that misses the other fails loudly instead of drifting silently.
"""

from pathlib import Path

# test-harness/tests/test_container_policy_sync.py -> repo root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]

CODEX_SUITE = (
    REPO_ROOT
    / "container"
    / "aarch64-darwin-apple-container-codex-universal"
    / "container-suite.sh"
)
NIXOS_SUITE = (
    REPO_ROOT
    / "container"
    / "aarch64-darwin-apple-container-nixos-25.11"
    / "container-suite.sh"
)


def test_container_suite_policy_scripts_are_byte_identical():
    assert CODEX_SUITE.read_bytes() == NIXOS_SUITE.read_bytes(), (
        "The two container-suite.sh files diverged. They are intentionally "
        "byte-identical policy scripts: the same fail-fast suite policy, "
        "applied to each container solution separately per ADR 0005's "
        "separate-implementations rule. If this divergence is deliberate, "
        "update this test AND "
        "docs/adr/0005-separate-container-implementations.md."
    )
