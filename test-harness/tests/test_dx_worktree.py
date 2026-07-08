"""Real end-to-end tests for `bin/dx-worktree` (container and worktree
safety).

Unlike the container-suite.sh failure-policy changes (which cannot be
exercised end-to-end on this host because the Apple `container` runtime does
not exist here), `dx-worktree` only shells out to `git`, so these tests drive
the real script against real scratch git repositories under `tmp_path`. They
never touch this repository itself.

Skip-free by design, matching test_runner_behavioral_parity.py: if `git` is
missing from PATH, that is a hard failure (`pytest.fail`), not a skip.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# test-harness/tests/test_dx_worktree.py -> repo root is two levels up.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DX_WORKTREE = _REPO_ROOT / "bin" / "dx-worktree"


def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        pytest.fail(
            f"required binary '{name}' not found on PATH; dx-worktree tests "
            "must not silently skip"
        )
    return path


def _git_env() -> dict[str, str]:
    """A minimal, isolated environment for driving git: real PATH (so git
    itself and any shell built-ins resolve), but explicit committer identity
    via GIT_* variables instead of depending on global git config."""
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "dx-worktree-test",
            "GIT_AUTHOR_EMAIL": "dx-worktree-test@example.invalid",
            "GIT_COMMITTER_NAME": "dx-worktree-test",
            "GIT_COMMITTER_EMAIL": "dx-worktree-test@example.invalid",
        }
    )
    return env


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    git = _require_binary("git")
    result = subprocess.run(
        [git, *args],
        cwd=str(cwd),
        env=_git_env(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"git {args} failed in {cwd}: {result.stdout}\n{result.stderr}"
    )
    return result


def init_scratch_repo(tmp_path: Path, extra_dirs: tuple[str, ...] = ()) -> Path:
    """Create a real git repo on branch `main` with a `common/` and `bin/`
    directory (dx-worktree always includes these) plus any requested extra
    directories, each containing a placeholder file, and one commit."""
    repo = tmp_path / "scratch-repo"
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], repo)

    (repo / "common").mkdir()
    (repo / "common" / "placeholder.txt").write_text("common\n")
    (repo / "bin").mkdir()
    (repo / "bin" / "placeholder.txt").write_text("bin\n")
    for extra in extra_dirs:
        d = repo / extra
        d.mkdir(parents=True, exist_ok=True)
        (d / "placeholder.txt").write_text(f"{extra}\n")

    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "initial commit"], repo)
    return repo


def run_dxw(
    args: list[str], cwd: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    script = str(_DX_WORKTREE)
    env = _git_env()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [script, *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        [
            _require_binary("git"),
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
        ],
        cwd=str(repo),
        env=_git_env(),
    )
    return result.returncode == 0


def test_dx_worktree_script_exists_and_is_executable():
    assert _DX_WORKTREE.is_file(), _DX_WORKTREE
    assert os.access(_DX_WORKTREE, os.X_OK), f"{_DX_WORKTREE} is not executable"


# --- destroy: safe (non-force) branch deletion -----------------------------


def test_destroy_merged_branch_succeeds_without_force(tmp_path):
    repo = init_scratch_repo(tmp_path)

    create = run_dxw(["create", "merged-task"], repo)
    assert create.returncode == 0, create.stderr
    assert branch_exists(repo, "agent/merged-task")

    # No commits were added on the branch, so it is identical to (and
    # therefore fully merged into) main: safe deletion must succeed.
    destroy = run_dxw(["destroy", "merged-task"], repo)
    assert destroy.returncode == 0, destroy.stderr
    assert not branch_exists(repo, "agent/merged-task")
    assert not (repo / ".worktrees" / "merged-task").exists()


def test_destroy_unmerged_branch_fails_without_force_and_succeeds_with_force(
    tmp_path,
):
    repo = init_scratch_repo(tmp_path)

    create = run_dxw(["create", "unmerged-task"], repo)
    assert create.returncode == 0, create.stderr

    worktree = repo / ".worktrees" / "unmerged-task"
    (worktree / "common" / "new-file.txt").write_text("unmerged change\n")
    _git(["add", "common/new-file.txt"], worktree)
    _git(["commit", "-q", "-m", "unmerged commit"], worktree)

    # Without --force: the branch has a commit not merged anywhere else, so
    # safe deletion must refuse and name --force in its message.
    destroy_no_force = run_dxw(["destroy", "unmerged-task"], repo)
    assert destroy_no_force.returncode != 0
    assert "--force" in destroy_no_force.stderr
    assert branch_exists(repo, "agent/unmerged-task"), (
        "branch must survive a refused safe deletion"
    )

    # With --force: deletion must succeed even though it is unmerged, and
    # must also finish removing the worktree if it wasn't already gone.
    destroy_forced = run_dxw(["destroy", "unmerged-task", "--force"], repo)
    assert destroy_forced.returncode == 0, destroy_forced.stderr
    assert not branch_exists(repo, "agent/unmerged-task")
    assert not worktree.exists()


# --- create: partial-worktree cleanup on a failed setup step ---------------


def _git_stub_failing_at_sparse_checkout_set(tmp_path: Path) -> dict[str, str]:
    """Build a PATH-shimmed fake `git` that transparently forwards every
    call to the real git binary except `git sparse-checkout set`, which it
    fails deliberately -- simulating a setup step failing partway through
    `dx-worktree create`, after the worktree and branch already exist."""
    real_git = _require_binary("git")
    stub_dir = tmp_path / "git-stub"
    stub_dir.mkdir()
    stub = stub_dir / "git"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "sparse-checkout" && "$2" == "set" ]]; then\n'
        '  echo "stub-git: simulated sparse-checkout set failure" >&2\n'
        "  exit 1\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n'
    )
    stub.chmod(0o755)
    env = _git_env()
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    return env


def test_create_cleans_up_partial_worktree_on_sparse_checkout_failure(tmp_path):
    repo = init_scratch_repo(tmp_path)
    stub_env = _git_stub_failing_at_sparse_checkout_set(tmp_path)

    result = run_dxw(["create", "sparse-fail-task"], repo, extra_env=stub_env)

    assert result.returncode != 0
    assert "cleaning up" in result.stderr
    # No debris: neither the worktree directory nor the branch survive.
    assert not (repo / ".worktrees" / "sparse-fail-task").exists()
    assert not branch_exists(repo, "agent/sparse-fail-task")
    # git's own worktree bookkeeping must not retain a dangling entry either.
    worktree_list = subprocess.run(
        [_require_binary("git"), "worktree", "list"],
        cwd=str(repo),
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    assert "sparse-fail-task" not in worktree_list.stdout

    # A retry with the same task name must start clean and succeed.
    retry = run_dxw(["create", "sparse-fail-task"], repo)
    assert retry.returncode == 0, retry.stderr
    assert branch_exists(repo, "agent/sparse-fail-task")


def test_create_does_not_delete_a_preexisting_branch_on_failure(tmp_path):
    """If `create` fails before ever creating a branch (name collision with
    a branch that already existed for an unrelated reason), cleanup must not
    delete that pre-existing branch."""
    repo = init_scratch_repo(tmp_path)
    _git(["branch", "agent/collide-task"], repo)

    result = run_dxw(["create", "collide-task"], repo)

    assert result.returncode != 0
    # The pre-existing branch must still be there -- create never owned it.
    assert branch_exists(repo, "agent/collide-task")


# --- sparse path validation by segment, not substring ----------------------


def test_sparse_path_with_double_dot_in_name_is_accepted(tmp_path):
    repo = init_scratch_repo(tmp_path, extra_dirs=("docs/foo..bar",))

    result = run_dxw(["create", "seg-ok-task", "docs/foo..bar"], repo)

    assert result.returncode == 0, result.stderr
    assert "docs/foo..bar" in result.stdout
    assert branch_exists(repo, "agent/seg-ok-task")


@pytest.mark.parametrize("bad_path", ["../escape", "a/../b"])
def test_sparse_path_traversal_segment_is_rejected(tmp_path, bad_path):
    repo = init_scratch_repo(tmp_path, extra_dirs=("a",))

    result = run_dxw(["create", "seg-bad-task", bad_path], repo)

    assert result.returncode != 0
    assert "'..'" in result.stderr
    assert bad_path in result.stderr
    # The whole create must fail -- no silent partial success that drops the
    # bad path but still reports success (constitution.md §4).
    assert not branch_exists(repo, "agent/seg-bad-task")
    assert not (repo / ".worktrees" / "seg-bad-task").exists()


def test_sparse_path_absolute_is_still_rejected(tmp_path):
    repo = init_scratch_repo(tmp_path)

    result = run_dxw(["create", "abs-bad-task", "/etc"], repo)

    assert result.returncode != 0
    assert not branch_exists(repo, "agent/abs-bad-task")


def test_sparse_path_bare_top_level_file_is_silently_fine(tmp_path):
    """A bare top-level file argument is a deliberate no-op (cone-mode
    sparse-checkout already always includes root-level files), not a
    rejection -- create must still succeed."""
    repo = init_scratch_repo(tmp_path)
    (repo / "toplevel.txt").write_text("x\n")
    _git(["add", "toplevel.txt"], repo)
    _git(["commit", "-q", "-m", "add toplevel file"], repo)

    result = run_dxw(["create", "toplevel-task", "toplevel.txt"], repo)

    assert result.returncode == 0, result.stderr
    assert branch_exists(repo, "agent/toplevel-task")
