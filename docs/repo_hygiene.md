# Repository Hygiene

Before backend work or promotion, run:

```powershell
python scripts/check_clean_worktree.py
git worktree list --porcelain
git status --short
```

Expected state:

- A single operational worktree: `cognia_app`.
- No active merge, rebase, or cherry-pick.
- No modified protected files unless the task explicitly authorizes them.
- No local generated outputs in `artifacts/`, `reports/generated/`, `reports/tmp/`, `reports/ops/`, or `screenshots/`.

If the tree is dirty, create an external backup under:

```text
%USERPROFILE%\Documents\cognia_git_safety_backup\
```

Then restore unrelated tracked files from the intended remote baseline and move local generated outputs outside the repository.
