#!/usr/bin/env python3
import os
from pathlib import Path

from api.app import create_app
from app.models import QuestionnaireCase, QuestionnaireSession, QuestionnaireSessionResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _normalize_label(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _safe_boolean(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    os.chdir(PROJECT_ROOT)
    app = create_app()
    with app.app_context():
        session_rows = QuestionnaireSession.query.all()
        result_rows = QuestionnaireSessionResult.query.all()
        case_rows = QuestionnaireCase.query.all()

        synthetic_sessions = [row for row in session_rows if _safe_boolean(row.metadata_json and row.metadata_json.get("synthetic"))]
        synthetic_results = [row for row in result_rows if _safe_boolean(row.metadata_json and row.metadata_json.get("synthetic"))]

        summary_pattern = [row for row in result_rows if row.summary_text and "patron orientativo sintetico" in row.summary_text.lower()]
        child_labels = [row for row in case_rows if _normalize_label(row.private_label) in {"hijo 1", "hijo 2", "hijo 3"}]

        print("SYNTHETIC DATA AUDIT")
        print("====================")
        print(f"Total questionnaire sessions: {len(session_rows)}")
        print(f"Total questionnaire results: {len(result_rows)}")
        print(f"Synthetic session records (metadata synthetic=true): {len(synthetic_sessions)}")
        print(f"Synthetic result records (metadata synthetic=true): {len(synthetic_results)}")
        print(f"Result summaries containing 'Patron orientativo sintetico': {len(summary_pattern)}")
        print(f"Case labels matching 'hijo 1', 'hijo 2', 'hijo 3': {len(child_labels)}")

        if synthetic_sessions:
            print("\nSample synthetic session IDs:")
            for session in synthetic_sessions[:10]:
                print(f" - {session.questionnaire_public_id} ({session.id})")

        if synthetic_results:
            print("\nSample synthetic result session IDs:")
            for result in synthetic_results[:10]:
                print(f" - session_id={result.session_id} result_id={result.id}")

        if summary_pattern:
            print("\nSample result summaries matching pattern:")
            for result in summary_pattern[:10]:
                print(f" - session_id={result.session_id} summary={result.summary_text[:120]!r}")

        if child_labels:
            print("\nMatching case labels:")
            for case in child_labels[:10]:
                print(f" - {case.case_public_id} label={case.private_label!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
