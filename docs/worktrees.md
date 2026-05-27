# Sparse worktrees

This repository is a monorepo. `common/`, `python/`, `javascript/`, `rust/`,
and `test-harness/` are normal tracked directories, not git submodules.

For isolated agent work, create a sparse worktree under `.worktrees/<task>/`.
The sparse checkout materializes only the directories needed for that
workstream, plus root-level files, `bin/`, and `common/`.

```bash
bin/dx-worktree create rust-bindgen rust
cd .worktrees/rust-bindgen
```

Inside that worktree, `python/`, `javascript/`, and `test-harness/` are absent
from the filesystem. A workstream that needs multiple areas can name them all:

```bash
bin/dx-worktree create contract-change common python javascript rust test-harness
```

To remove a worktree and its `agent/<task>` branch:

```bash
bin/dx-worktree destroy rust-bindgen
```

Sparse-checkout controls which paths are materialized in a worktree. It is not
a security boundary by itself. An agent can still reach paths outside the
worktree if its execution harness allows absolute paths or `cd ..`; enforce
that separately in the harness when path isolation matters.

Commands such as `git fetch` and `git pull` still operate on the full
repository. Hidden directories also reappear if sparse-checkout is disabled or
the worktree is replaced with a full checkout.
