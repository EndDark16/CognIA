from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROTECTED_PATHS = {
    "scripts/hardening_second_pass.py",
    "scripts/rebuild_dsm5_exact_datasets.py",
    "scripts/run_pipeline.py",
    "scripts/seed_users.py",
    "tests/test_health.py",
}

GENERATED_PREFIXES = (
    "artifacts/",
    "reports/generated/",
    "reports/tmp/",
    "reports/ops/",
    "screenshots/",
)

GENERATED_SUFFIXES = (".log", ".tmp", ".pdf.tmp")


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _porcelain_entries() -> list[tuple[str, str]]:
    result = _run_git(["status", "--porcelain=v1"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        status = line[:2].strip()
        path = line[3:].strip().replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append((status, path))
    return entries


def _is_generated(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith(GENERATED_PREFIXES) or normalized.endswith(GENERATED_SUFFIXES)


def validate(allow_dirty: bool = False) -> list[str]:
    errors: list[str] = []
    entries = _porcelain_entries()
    if entries and not allow_dirty:
        errors.append("worktree_dirty")

    protected_changes = [path for _, path in entries if path in PROTECTED_PATHS]
    if protected_changes:
        errors.append("protected_files_modified:" + ",".join(sorted(protected_changes)))

    generated_changes = [path for _, path in entries if _is_generated(path)]
    if generated_changes:
        errors.append("generated_outputs_present:" + ",".join(sorted(generated_changes)))

    for head_name in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD"):
        result = _run_git(["rev-parse", "-q", "--verify", head_name])
        if result.returncode == 0:
            errors.append(f"git_operation_active:{head_name}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CognIA repository hygiene before backend work.")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow generic dirty worktree while still blocking protected/generated files and active Git operations.",
    )
    args = parser.parse_args()

    if not Path(".git").exists():
        print("error: run this command at the repository root", file=sys.stderr)
        return 2

    errors = validate(allow_dirty=args.allow_dirty)
    if errors:
        print("Repository hygiene check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
