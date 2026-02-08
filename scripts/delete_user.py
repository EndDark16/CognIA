import argparse
import sys
from typing import Iterable

from api.app import create_app
from config.settings import DevelopmentConfig
from app.models import (
    db,
    AppUser,
    UserRole,
    RefreshToken,
    UserSession,
    UserMFA,
    RecoveryCode,
    MFALoginChallenge,
    PasswordResetToken,
    SubjectGuardian,
    AuditLog,
    Evaluation,
    EvaluationResponse,
    EvaluationPrediction,
    EvaluationPredictionDetail,
    RiskAlert,
    EvaluationReport,
    PsychologistFeedback,
    MLModelVersion,
    DiagnosticThreshold,
)


def _ids(query) -> list:
    return [row[0] for row in query]


def _delete_where(model, *criteria) -> int:
    return model.query.filter(*criteria).delete(synchronize_session=False)


def _delete_by_ids(model, field, ids: Iterable) -> int:
    if not ids:
        return 0
    return model.query.filter(field.in_(ids)).delete(synchronize_session=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete a user and dependent records.")
    parser.add_argument("--username", help="Username to delete")
    parser.add_argument("--email", help="Email to delete")
    parser.add_argument(
        "--deactivate-if-blocked",
        action="store_true",
        help="If deletion fails, deactivate the user instead of raising.",
    )
    args = parser.parse_args()

    if not args.username and not args.email:
        print("Provide --username or --email")
        return 1

    app = create_app(DevelopmentConfig)
    with app.app_context():
        user = AppUser.query.filter(
            (AppUser.username == args.username) if args.username else False
            | (AppUser.email == args.email) if args.email else False
        ).first()
        if not user:
            print("User not found")
            return 0

        user_id = user.id
        deleted = {}

        try:
            deleted["user_role"] = _delete_where(UserRole, UserRole.user_id == user_id)
            deleted["refresh_token"] = _delete_where(RefreshToken, RefreshToken.user_id == user_id)
            deleted["user_session"] = _delete_where(UserSession, UserSession.user_id == user_id)
            deleted["user_mfa"] = _delete_where(UserMFA, UserMFA.user_id == user_id)
            deleted["recovery_code"] = _delete_where(RecoveryCode, RecoveryCode.user_id == user_id)
            deleted["mfa_login_challenge"] = _delete_where(MFALoginChallenge, MFALoginChallenge.user_id == user_id)
            deleted["password_reset_token"] = _delete_where(
                PasswordResetToken, PasswordResetToken.user_id == user_id
            )
            deleted["subject_guardian"] = _delete_where(SubjectGuardian, SubjectGuardian.user_id == user_id)
            deleted["audit_log"] = _delete_where(AuditLog, AuditLog.user_id == user_id)

            eval_ids = _ids(
                db.session.query(Evaluation.id).filter(
                    (Evaluation.requested_by_user_id == user_id)
                    | (Evaluation.psychologist_id == user_id)
                )
            )
            pred_ids = _ids(
                db.session.query(EvaluationPrediction.id).filter(
                    EvaluationPrediction.evaluation_id.in_(eval_ids)
                )
            )

            deleted["risk_alert"] = _delete_by_ids(RiskAlert, RiskAlert.evaluation_id, eval_ids)
            deleted["evaluation_prediction_detail"] = _delete_by_ids(
                EvaluationPredictionDetail, EvaluationPredictionDetail.evaluation_prediction_id, pred_ids
            )
            deleted["evaluation_prediction"] = _delete_by_ids(
                EvaluationPrediction, EvaluationPrediction.evaluation_id, eval_ids
            )
            deleted["evaluation_response"] = _delete_by_ids(
                EvaluationResponse, EvaluationResponse.evaluation_id, eval_ids
            )
            deleted["evaluation_report"] = _delete_by_ids(
                EvaluationReport, EvaluationReport.evaluation_id, eval_ids
            )
            deleted["psychologist_feedback"] = _delete_where(
                PsychologistFeedback, PsychologistFeedback.psychologist_id == user_id
            )
            deleted["evaluation_requested"] = _delete_where(
                Evaluation, Evaluation.requested_by_user_id == user_id
            )
            deleted["evaluation_psychologist"] = _delete_where(
                Evaluation, Evaluation.psychologist_id == user_id
            )
            deleted["evaluation_report_created"] = _delete_where(
                EvaluationReport, EvaluationReport.created_by_user_id == user_id
            )
            deleted["ml_model_version_trained"] = _delete_where(
                MLModelVersion, MLModelVersion.trained_by_user_id == user_id
            )
            deleted["diagnostic_threshold_created"] = _delete_where(
                DiagnosticThreshold, DiagnosticThreshold.created_by_user_id == user_id
            )

            db.session.delete(user)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            if args.deactivate_if_blocked:
                user.is_active = False
                db.session.add(user)
                db.session.commit()
                print(f"Delete blocked ({exc}); user deactivated instead.")
                return 0
            print(f"Delete failed: {exc}")
            return 2

        print(f"User deleted: {user.username} ({user.email})")
        for k, v in deleted.items():
            if v:
                print(f"- {k}: {v}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
