import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_clean_worktree.py"
SPEC = importlib.util.spec_from_file_location("check_clean_worktree", SCRIPT_PATH)
check_clean_worktree = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(check_clean_worktree)
_is_generated = check_clean_worktree._is_generated


def test_generated_output_detection():
    assert _is_generated("artifacts/local_synthetic_dashboard_summary.json")
    assert _is_generated("reports/generated/dashboard.json")
    assert _is_generated("reports/tmp/run.log")
    assert _is_generated("screenshots/dashboard.png")
    assert _is_generated("api/debug.tmp")


def test_source_paths_are_not_generated_outputs():
    assert not _is_generated("api/app.py")
    assert not _is_generated("reports/final_closure/summary.md")
