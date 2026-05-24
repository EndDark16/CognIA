from __future__ import annotations

import argparse
import hashlib
import os
from collections import Counter
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.app import create_app
from api.services.colombia_locations import (
    infer_department_city_from_text,
    resolve_department_city,
)
from app.models import AppUser, db


DEFAULT_ROLES = ("guardian", "psychologist", "admin")
DEFAULT_LOCATION_DISTRIBUTION = (
    ("Bogota D.C.", "Bogota", 55),
    ("Cundinamarca", "Facatativa", 30),
    ("Cundinamarca", "Madrid", 5),
    ("Cundinamarca", "Mosquera", 5),
    ("Cundinamarca", "Funza", 5),
)
CITY_HINTS = {
    "bogota": ("Bogota D.C.", "Bogota"),
    "facatativa": ("Cundinamarca", "Facatativa"),
    "madrid": ("Cundinamarca", "Madrid"),
    "mosquera": ("Cundinamarca", "Mosquera"),
    "funza": ("Cundinamarca", "Funza"),
    "chia": ("Cundinamarca", "Chia"),
    "soacha": ("Cundinamarca", "Soacha"),
    "zipaquira": ("Cundinamarca", "Zipaquira"),
}


def _config_class_from_env():
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def _looks_like_production(app) -> bool:
    uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
    env_name = str(app.config.get("ENV") or "")
    if "prod" in uri.lower() or "prod" in env_name.lower():
        return True
    if "supabase.co" in uri.lower() and "localhost" not in uri.lower():
        return True
    return False


def _distribution_pick(seed: str) -> tuple[str, str]:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    cursor = 0
    for department, city, weight in DEFAULT_LOCATION_DISTRIBUTION:
        cursor += weight
        if bucket < cursor:
            return department, city
    return DEFAULT_LOCATION_DISTRIBUTION[0][0], DEFAULT_LOCATION_DISTRIBUTION[0][1]


def _hint_pick(user: AppUser) -> tuple[str | None, str | None]:
    hints = " ".join(
        [
            str(user.username or ""),
            str(user.email or ""),
            str(user.full_name or ""),
            str(user.location or ""),
            str(user.professional_location or ""),
            str(user.city or ""),
            str(user.department or ""),
            str(user.professional_city or ""),
            str(user.professional_department or ""),
        ]
    ).lower()
    for token, location in CITY_HINTS.items():
        if token in hints:
            return location
    return None, None


def _infer_location(user: AppUser) -> tuple[str, str]:
    try:
        dep, city = resolve_department_city(
            department=user.department,
            city=user.city,
            legacy_department=user.professional_department,
            legacy_city=user.professional_city,
            legacy_location=user.location or user.professional_location,
        )
        if dep and city:
            return dep, city
    except Exception:
        pass

    parsed_dep, parsed_city = infer_department_city_from_text(user.location or user.professional_location)
    if parsed_dep and parsed_city:
        return parsed_dep, parsed_city

    hint_dep, hint_city = _hint_pick(user)
    if hint_dep and hint_city:
        return hint_dep, hint_city
    return _distribution_pick(str(user.id))


def _parse_roles(raw_roles: str | None) -> tuple[str, ...]:
    if not raw_roles:
        return DEFAULT_ROLES
    parts = [part.strip().lower() for part in raw_roles.split(",") if part.strip()]
    allowed = {"guardian", "psychologist", "admin"}
    return tuple(role for role in parts if role in allowed) or DEFAULT_ROLES


def _has_any_protected_role(user: AppUser, selected_roles: tuple[str, ...]) -> bool:
    role_names = {str(role.name or "").strip().upper() for role in user.roles}
    if "guardian" in selected_roles and "GUARDIAN" in role_names:
        return True
    if "psychologist" in selected_roles and "PSYCHOLOGIST" in role_names:
        return True
    if "admin" in selected_roles and "ADMIN" in role_names:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill user department/city with Colombia canonical locations.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only (default behavior).")
    parser.add_argument("--execute", action="store_true", help="Persist updates to database.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of users to update.")
    parser.add_argument("--roles", type=str, default="guardian,psychologist,admin")
    parser.add_argument("--include-real-users", action="store_true", help="Allow updating non synthetic users.")
    parser.add_argument(
        "--only-missing-location",
        action="store_true",
        default=True,
        help="Only update users missing department/city (default true).",
    )
    parser.add_argument(
        "--i-understand-this-updates-users",
        action="store_true",
        help="Mandatory when --execute against production-like databases.",
    )
    args = parser.parse_args()

    run_execute = bool(args.execute)
    if not run_execute:
        args.dry_run = True

    app = create_app(_config_class_from_env())
    with app.app_context():
        if run_execute and _looks_like_production(app) and not args.i_understand_this_updates_users:
            print("[backfill-user-locations] blocked: production-like database requires --i-understand-this-updates-users")
            return 2

        selected_roles = _parse_roles(args.roles)
        users_query = AppUser.query.order_by(AppUser.created_at.asc().nullslast(), AppUser.id.asc())
        users = users_query.all()
        total_users = len(users)

        candidates: list[tuple[AppUser, str, str]] = []
        before_by_role = Counter()
        for user in users:
            if not _has_any_protected_role(user, selected_roles):
                continue
            role_key = str(user.user_type or "unknown")
            before_by_role[role_key] += 1
            if args.only_missing_location and user.department and user.city:
                continue
            if not args.include_real_users and "synthetic" not in str(user.username or "").lower():
                continue
            dep, city = _infer_location(user)
            candidates.append((user, dep, city))

        if args.limit and args.limit > 0:
            candidates = candidates[: args.limit]

        print(f"[backfill-user-locations] total_users={total_users}")
        print(f"[backfill-user-locations] role_scope={','.join(selected_roles)}")
        print(f"[backfill-user-locations] candidates={len(candidates)}")
        print(f"[backfill-user-locations] mode={'execute' if run_execute else 'dry-run'}")
        print(f"[backfill-user-locations] only_missing_location={args.only_missing_location}")
        print(f"[backfill-user-locations] include_real_users={args.include_real_users}")

        planned_distribution = Counter((dep, city) for _, dep, city in candidates)
        for (dep, city), count in sorted(planned_distribution.items(), key=lambda item: (-item[1], item[0][0], item[0][1])):
            print(f"  plan {dep} / {city}: {count}")

        if not run_execute:
            return 0

        updated_by_role = Counter()
        for user, dep, city in candidates:
            user.department = dep
            user.city = city
            updated_by_role[str(user.user_type or "unknown")] += 1

        db.session.commit()

        print(f"[backfill-user-locations] updated={len(candidates)}")
        for role, count in sorted(updated_by_role.items()):
            print(f"  updated role={role}: {count}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
