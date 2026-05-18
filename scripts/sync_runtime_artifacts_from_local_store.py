from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_CSV = ROOT / "data" / "hybrid_active_modes_freeze_v17" / "tables" / "hybrid_active_models_30_modes.csv"
TARGET_MODELS_DIR = ROOT / "models" / "active_modes"


def _search_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        roots.append(resolved)

    raw = os.getenv("RUNTIME_ARTIFACT_SEARCH_ROOTS", "").strip()
    if raw:
        for chunk in raw.split(os.pathsep):
            item = chunk.strip()
            if item:
                _add(Path(item))

    if not roots:
        for default_root in (ROOT, ROOT.parent, Path("/opt/cognia"), Path("/opt")):
            _add(default_root)

    return [r for r in roots if r.exists()]


def _existing_joblib(slot_dir: Path) -> Path | None:
    for name in ("pipeline.joblib", "calibrated.joblib"):
        path = slot_dir / name
        if path.exists():
            return path
    files = sorted(slot_dir.glob("*.joblib"))
    return files[0] if files else None


def _search_candidate(model_key: str, roots: list[Path]) -> Path | None:
    preferred_patterns = (
        f"**/{model_key}/pipeline.joblib",
        f"**/{model_key}/calibrated.joblib",
        f"**/{model_key}/*.joblib",
    )
    for root in roots:
        for pattern in preferred_patterns:
            matches = sorted(root.glob(pattern))
            if matches:
                return matches[0]
    return None


def _sync_slot(model_key: str, roots: list[Path], dry_run: bool = False) -> tuple[str, str]:
    slot_dir = TARGET_MODELS_DIR / model_key
    slot_dir.mkdir(parents=True, exist_ok=True)

    current = _existing_joblib(slot_dir)
    if current is not None:
        return "already_present", str(current)

    source = _search_candidate(model_key, roots)
    if source is None:
        return "missing_source", ""

    target = slot_dir / source.name
    if not dry_run:
        shutil.copy2(source, target)
        meta_src = source.parent / "metadata.json"
        meta_dst = slot_dir / "metadata.json"
        if (not meta_dst.exists()) and meta_src.exists():
            shutil.copy2(meta_src, meta_dst)
    return "copied", str(target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync active runtime artifacts (joblib) from local host store.")
    parser.add_argument("--strict", action="store_true", help="Fail if any active slot remains unresolved.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and print plan without copying files.")
    args = parser.parse_args()

    if not ACTIVE_CSV.exists():
        raise FileNotFoundError(f"active models csv missing: {ACTIVE_CSV}")

    with ACTIVE_CSV.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        model_keys = sorted({str((row.get("active_model_id") or "")).strip() for row in reader if row.get("active_model_id")})
    if not model_keys:
        raise RuntimeError("active_model_id list is empty")

    roots = _search_roots()
    print(f"[sync-runtime-artifacts] search_roots={len(roots)}")
    for root in roots:
        print(f" - {root}")

    copied = 0
    already = 0
    missing: list[str] = []

    for model_key in model_keys:
        status, path = _sync_slot(model_key, roots=roots, dry_run=args.dry_run)
        if status == "copied":
            copied += 1
            print(f"[copied] {model_key} -> {path}")
        elif status == "already_present":
            already += 1
            print(f"[ok] {model_key} -> {path}")
        else:
            missing.append(model_key)
            print(f"[missing] {model_key}")

    print(
        "[sync-runtime-artifacts] summary "
        f"total={len(model_keys)} already_present={already} copied={copied} missing={len(missing)}"
    )
    if missing:
        print("[sync-runtime-artifacts] missing_model_keys:")
        for item in missing:
            print(f" - {item}")

    if args.strict and missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
