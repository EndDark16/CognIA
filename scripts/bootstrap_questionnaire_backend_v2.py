import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.app import create_app
from api.services import questionnaire_v2_loader_service as loader_service
from api.services import questionnaire_v2_service as runtime_service
from app.models import DashboardAggregate, db


def _config_class_from_env():
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def cmd_load_questionnaire(args):
    stats = loader_service.sync_questionnaire_catalog(source_dir=Path(args.source_dir) if args.source_dir else None)
    db.session.commit()
    print(json.dumps({"ok": True, "action": "load_questionnaire", "stats": stats}, indent=2))


def cmd_load_models(args):
    stats = loader_service.sync_active_models()
    db.session.commit()
    print(json.dumps({"ok": True, "action": "load_models", "stats": stats}, indent=2))


def cmd_load_all(args):
    stats = loader_service.bootstrap_questionnaire_backend_v2(source_dir=Path(args.source_dir) if args.source_dir else None)
    print(json.dumps({"ok": True, "action": "load_all", "stats": stats}, indent=2))


def cmd_regenerate_report_snapshot(args):
    months = int(args.months)
    dataset = runtime_service.dashboard_adoption_history(months=months)
    period_end = date.today()
    period_start = date(period_end.year, period_end.month, 1)

    row = DashboardAggregate(
        aggregate_key="adoption_history",
        period_start=period_start,
        period_end=period_end,
        value_numeric=None,
        value_json=dataset,
        computed_at=datetime.now(timezone.utc),
    )
    db.session.add(row)
    db.session.commit()

    print(json.dumps({"ok": True, "action": "regenerate_report_snapshot", "months": months}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Bootstrap questionnaire backend v2")
    sub = parser.add_subparsers(dest="command", required=True)

    p_q = sub.add_parser("load-questionnaire", help="Load questionnaire/scales from CSV")
    p_q.add_argument("--source-dir", default=str(loader_service.DEFAULT_SOURCE_DIR))
    p_q.set_defaults(func=cmd_load_questionnaire)

    p_m = sub.add_parser("load-models", help="Register active models from operational CSV")
    p_m.set_defaults(func=cmd_load_models)

    p_a = sub.add_parser("load-all", help="Load questionnaire + models")
    p_a.add_argument("--source-dir", default=str(loader_service.DEFAULT_SOURCE_DIR))
    p_a.set_defaults(func=cmd_load_all)

    p_r = sub.add_parser("regenerate-report-snapshot", help="Regenerate adoption history snapshot")
    p_r.add_argument("--months", default=12, type=int)
    p_r.set_defaults(func=cmd_regenerate_report_snapshot)

    args = parser.parse_args()

    app = create_app(_config_class_from_env())
    with app.app_context():
        args.func(args)


if __name__ == "__main__":
    main()
