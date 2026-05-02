import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

db = SQLAlchemy()

# Association table for multi-disorder questions
question_disorder = db.Table(
    "question_disorder",
    db.Column("question_id", UUID(as_uuid=True), db.ForeignKey("question.id", ondelete="CASCADE"), primary_key=True),
    db.Column("disorder_id", UUID(as_uuid=True), db.ForeignKey("disorder.id", ondelete="RESTRICT"), primary_key=True),
    db.Column("created_at", db.DateTime(timezone=True), server_default=func.now(), nullable=False),
)

# Modelos existentes reutilizados
class AppUser(db.Model):
    __tablename__ = 'app_user'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String, unique=True, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column("password_hash", db.String, nullable=False)
    full_name = db.Column(db.String)
    user_type = db.Column(db.String, nullable=False, default="guardian", server_default="guardian")
    professional_card_number = db.Column(db.String, unique=True)
    colpsic_verified = db.Column(db.Boolean, default=False, nullable=False)
    colpsic_verified_at = db.Column(db.DateTime(timezone=True))
    colpsic_verified_by = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    colpsic_rejected_at = db.Column(db.DateTime(timezone=True))
    colpsic_rejected_by = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    colpsic_reject_reason = db.Column(db.Text)
    sessions_revoked_at = db.Column(db.DateTime(timezone=True))
    failed_login_attempts = db.Column(db.Integer, nullable=False, server_default="0")
    last_failed_login_at = db.Column(db.DateTime(timezone=True))
    login_locked_until = db.Column(db.DateTime(timezone=True))
    password_changed_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, default=True)
    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_confirmed_at = db.Column(db.DateTime(timezone=True))
    mfa_method = db.Column(db.String, default="none")
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    roles = db.relationship('Role', secondary='user_role', backref='users')

class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String, unique=True, nullable=False)
    description = db.Column(db.String)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

class UserRole(db.Model):
    __tablename__ = 'user_role'
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('app_user.id'), primary_key=True)
    role_id = db.Column(UUID(as_uuid=True), db.ForeignKey('role.id'), primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

class UserSession(db.Model):
    __tablename__ = 'user_session'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('app_user.id'), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    ended_at = db.Column(db.DateTime(timezone=True))
    ip_address = db.Column(db.String)
    device_info = db.Column(db.String)
    ended_by_timeout = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('app_user.id'))
    action = db.Column(db.String, nullable=False)
    section = db.Column(db.String, nullable=False)
    details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

# Nuevo modelo RefreshToken
class RefreshToken(db.Model):
    __tablename__ = 'refresh_token'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti = db.Column(db.String, unique=True, nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('app_user.id'), nullable=False)
    revoked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())


class UserMFA(db.Model):
    __tablename__ = 'user_mfa'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('app_user.id'), unique=True, nullable=False)
    method = db.Column(db.String, default="totp", nullable=False)
    secret_encrypted = db.Column(db.String, nullable=False)
    last_used_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())


class RecoveryCode(db.Model):
    __tablename__ = 'recovery_code'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('app_user.id'), nullable=False)
    code_hash = db.Column(db.String, nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())


class MFALoginChallenge(db.Model):
    __tablename__ = 'mfa_login_challenge'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('app_user.id'), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    ip_address = db.Column(db.String)
    user_agent = db.Column(db.String)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())


class QuestionnaireTemplate(db.Model):
    __tablename__ = "questionnaire_template"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.Text, nullable=False)
    version = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    archived_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Question(db.Model):
    __tablename__ = "question"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    questionnaire_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_template.id"), nullable=False
    )
    code = db.Column(db.Text, nullable=False)
    text = db.Column(db.Text, nullable=False)
    response_type = db.Column(db.Text, nullable=False)
    disorder_id = db.Column(UUID(as_uuid=True))
    position = db.Column(db.Integer)
    response_min = db.Column(db.Numeric)
    response_max = db.Column(db.Numeric)
    response_step = db.Column(db.Numeric)
    response_options = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    disorders = db.relationship("Disorder", secondary=question_disorder, backref="questions")


class Disorder(db.Model):
    __tablename__ = "disorder"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = db.Column(db.Text, nullable=False)
    name = db.Column(db.Text, nullable=False)
    dsm_code = db.Column(db.Text)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Subject(db.Model):
    __tablename__ = "subject"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_code = db.Column(db.Text, nullable=False)
    birth_year = db.Column(db.Integer)
    sex = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Evaluation(db.Model):
    __tablename__ = "evaluation"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey("subject.id"))
    requested_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    psychologist_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    age_at_evaluation = db.Column(db.Integer, nullable=False)
    context = db.Column(db.Text)
    raw_symptoms = db.Column(db.JSON)
    processed_features = db.Column(db.JSON)
    evaluation_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    questionnaire_template_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_template.id"), nullable=False
    )
    registration_number = db.Column(db.Text, nullable=False)
    access_key_hash = db.Column(db.Text, nullable=False)
    access_key_created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    access_key_rotated_at = db.Column(db.DateTime(timezone=True))
    access_key_failed_attempts = db.Column(db.Integer, server_default="0", nullable=False)
    access_key_locked_until = db.Column(db.DateTime(timezone=True))
    requires_access_key_reset = db.Column(db.Boolean, server_default="true", nullable=False)


class EvaluationResponse(db.Model):
    __tablename__ = "evaluation_response"

    evaluation_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("evaluation.id"), primary_key=True
    )
    question_id = db.Column(UUID(as_uuid=True), db.ForeignKey("question.id"), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SubjectGuardian(db.Model):
    __tablename__ = "subject_guardian"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = db.Column(UUID(as_uuid=True), db.ForeignKey("subject.id"), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    relationship = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MLModel(db.Model):
    __tablename__ = "ml_model"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.Text, nullable=False)
    algorithm = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MLModelVersion(db.Model):
    __tablename__ = "ml_model_version"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ml_model_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ml_model.id"), nullable=False)
    version_tag = db.Column(db.Text, nullable=False)
    trained_at = db.Column(db.DateTime(timezone=True))
    trained_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    metrics = db.Column(db.JSON)
    model_artifact_path = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TrainingDataset(db.Model):
    __tablename__ = "training_dataset"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.Text, nullable=False)
    source = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TrainingRun(db.Model):
    __tablename__ = "training_run"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ml_model_version_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ml_model_version.id"), nullable=False)
    training_dataset_id = db.Column(UUID(as_uuid=True), db.ForeignKey("training_dataset.id"), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True))
    finished_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.Text, nullable=False)
    metrics = db.Column(db.JSON)
    log = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DiagnosticThreshold(db.Model):
    __tablename__ = "diagnostic_threshold"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disorder_id = db.Column(UUID(as_uuid=True), db.ForeignKey("disorder.id"), nullable=False)
    ml_model_version_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ml_model_version.id"), nullable=False)
    threshold_value = db.Column(db.Numeric(5, 4), nullable=False)
    created_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EvaluationPrediction(db.Model):
    __tablename__ = "evaluation_prediction"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = db.Column(UUID(as_uuid=True), db.ForeignKey("evaluation.id"), nullable=False)
    ml_model_version_id = db.Column(UUID(as_uuid=True), db.ForeignKey("ml_model_version.id"), nullable=False)
    predicted_at = db.Column(db.DateTime(timezone=True), nullable=False)
    overall_risk_score = db.Column(db.Numeric(5, 4))
    diagnostic_json = db.Column(db.JSON)
    explanation_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EvaluationPredictionDetail(db.Model):
    __tablename__ = "evaluation_prediction_detail"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_prediction_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("evaluation_prediction.id"), nullable=False
    )
    disorder_id = db.Column(UUID(as_uuid=True), db.ForeignKey("disorder.id"), nullable=False)
    probability = db.Column(db.Numeric(5, 4), nullable=False)
    label = db.Column(db.Text, nullable=False)
    risk_level = db.Column(db.Text, nullable=False)
    threshold_value = db.Column(db.Numeric(5, 4), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EvaluationReport(db.Model):
    __tablename__ = "evaluation_report"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = db.Column(UUID(as_uuid=True), db.ForeignKey("evaluation.id"), nullable=False)
    type = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmailLog(db.Model):
    __tablename__ = "email_log"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_report_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("evaluation_report.id"), nullable=False
    )
    recipient_email = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.Text, nullable=False)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmailDeliveryLog(db.Model):
    __tablename__ = "email_delivery_log"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template = db.Column(db.Text, nullable=False)
    recipient_email = db.Column(db.Text, nullable=False)
    subject = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True))


class EmailUnsubscribe(db.Model):
    __tablename__ = "email_unsubscribe"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String, unique=True, nullable=False, index=True)
    reason = db.Column(db.Text)
    source = db.Column(db.String)
    request_ip = db.Column(db.String)
    user_agent = db.Column(db.String)
    unsubscribed_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_token"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False, index=True)
    token_hash = db.Column(db.String, nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    used_at = db.Column(db.DateTime(timezone=True))
    request_ip = db.Column(db.String)
    user_agent = db.Column(db.String)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)


class PsychologistFeedback(db.Model):
    __tablename__ = "psychologist_feedback"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = db.Column(UUID(as_uuid=True), db.ForeignKey("evaluation.id"), nullable=False)
    psychologist_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    agrees_with_model = db.Column(db.Boolean, nullable=False)
    final_diagnosis_json = db.Column(db.JSON)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RiskAlert(db.Model):
    __tablename__ = "risk_alert"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = db.Column(UUID(as_uuid=True), db.ForeignKey("evaluation.id"), nullable=False)
    evaluation_prediction_detail_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("evaluation_prediction_detail.id"), nullable=False
    )
    risk_level = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    notified_psychologist_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False
    )
    resolved_at = db.Column(db.DateTime(timezone=True))
    resolved_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    resolution_notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SyntheticDataBatch(db.Model):
    __tablename__ = "synthetic_data_batch"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    parameters = db.Column(db.JSON, nullable=False)
    sample_count = db.Column(db.Integer, nullable=False)
    results = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SystemSetting(db.Model):
    __tablename__ = "system_setting"

    key = db.Column(db.Text, primary_key=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ==========================
# Questionnaire Runtime v1
# ==========================


class QRQuestionnaireTemplate(db.Model):
    __tablename__ = "qr_questionnaire_template"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    created_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QRQuestionnaireVersion(db.Model):
    __tablename__ = "qr_questionnaire_version"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_questionnaire_template.id", ondelete="CASCADE"), nullable=False
    )
    version_label = db.Column(db.String(64), nullable=False)
    changelog = db.Column(db.Text)
    status = db.Column(db.String(32), nullable=False, server_default="draft")
    is_published = db.Column(db.Boolean, nullable=False, server_default="false")
    published_at = db.Column(db.DateTime(timezone=True))
    created_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("template_id", "version_label", name="uq_qr_template_version_label"),
    )


class QRDisclosureVersion(db.Model):
    __tablename__ = "qr_disclosure_version"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    questionnaire_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_questionnaire_version.id", ondelete="CASCADE"), nullable=False
    )
    disclosure_type = db.Column(db.String(40), nullable=False)
    version_label = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content_markdown = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    created_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint(
            "questionnaire_version_id",
            "disclosure_type",
            "version_label",
            name="uq_qr_disclosure_version",
        ),
    )


class QRQuestionnaireSection(db.Model):
    __tablename__ = "qr_questionnaire_section"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    questionnaire_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_questionnaire_version.id", ondelete="CASCADE"), nullable=False
    )
    key = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    position = db.Column(db.Integer, nullable=False)
    is_required = db.Column(db.Boolean, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("questionnaire_version_id", "key", name="uq_qr_section_key"),
    )


class QRQuestion(db.Model):
    __tablename__ = "qr_question"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_questionnaire_section.id", ondelete="CASCADE"), nullable=False
    )
    key = db.Column(db.String(150), nullable=False)
    feature_key = db.Column(db.String(150), nullable=False)
    domain = db.Column(db.String(40), nullable=False, server_default="general")
    prompt = db.Column(db.Text, nullable=False)
    help_text = db.Column(db.Text)
    response_type = db.Column(db.String(40), nullable=False)
    requiredness = db.Column(db.String(20), nullable=False, server_default="required")
    position = db.Column(db.Integer, nullable=False)
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    step_value = db.Column(db.Float)
    allowed_values = db.Column(db.JSON)
    visibility_rule = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("section_id", "key", name="uq_qr_question_key"),
    )


class QRQuestionOption(db.Model):
    __tablename__ = "qr_question_option"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = db.Column(UUID(as_uuid=True), db.ForeignKey("qr_question.id", ondelete="CASCADE"), nullable=False)
    option_value = db.Column(db.String(120), nullable=False)
    option_label = db.Column(db.String(255), nullable=False)
    position = db.Column(db.Integer, nullable=False, server_default="1")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("question_id", "option_value", name="uq_qr_question_option_value"),
    )


class QREvaluation(db.Model):
    __tablename__ = "qr_evaluation"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    questionnaire_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_questionnaire_version.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False, index=True)
    psychologist_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), index=True)
    respondent_type = db.Column(db.String(40), nullable=False, server_default="caregiver")
    child_age_years = db.Column(db.Integer, nullable=False)
    child_sex_assigned_at_birth = db.Column(db.String(32), nullable=False, server_default="Unknown")

    status = db.Column(db.String(40), nullable=False, server_default="draft", index=True)
    review_tag = db.Column(db.String(40), nullable=False, server_default="sin_revisar")
    deleted_by_user = db.Column(db.Boolean, nullable=False, server_default="false", index=True)
    deleted_at = db.Column(db.DateTime(timezone=True))

    reference_id = db.Column(db.String(24), nullable=False, unique=True, index=True)
    pin_hash = db.Column(db.String(255), nullable=False)
    pin_failed_attempts = db.Column(db.Integer, nullable=False, server_default="0")
    pin_locked_until = db.Column(db.DateTime(timezone=True))

    consent_disclosure_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_disclosure_version.id", ondelete="RESTRICT"), nullable=False
    )
    pre_disclaimer_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_disclosure_version.id", ondelete="RESTRICT"), nullable=False
    )
    result_disclaimer_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_disclosure_version.id", ondelete="RESTRICT"), nullable=False
    )
    pdf_disclaimer_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_disclosure_version.id", ondelete="RESTRICT"), nullable=False
    )
    consent_accepted_at = db.Column(db.DateTime(timezone=True))

    runtime_scope_version = db.Column(db.String(64), nullable=False, server_default="questionnaire_runtime_v1")
    model_runtime_bundle = db.Column(db.String(120), nullable=False, server_default="qr_runtime_bundle_v1")
    processing_attempts = db.Column(db.Integer, nullable=False, server_default="0")
    processing_error = db.Column(db.Text)
    processing_started_at = db.Column(db.DateTime(timezone=True))
    processing_finished_at = db.Column(db.DateTime(timezone=True))

    is_waiting_live_result = db.Column(db.Boolean, nullable=False, server_default="true")
    last_presence_heartbeat_at = db.Column(db.DateTime(timezone=True))
    notify_if_user_offline = db.Column(db.Boolean, nullable=False, server_default="true")

    retention_until = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QREvaluationResponse(db.Model):
    __tablename__ = "qr_evaluation_response"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id = db.Column(UUID(as_uuid=True), db.ForeignKey("qr_question.id", ondelete="RESTRICT"), nullable=False)
    section_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_questionnaire_section.id", ondelete="RESTRICT"), nullable=False
    )
    answer_raw = db.Column(db.JSON, nullable=False)
    answer_normalized = db.Column(db.Text, nullable=False)
    answered_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("evaluation_id", "question_id", name="uq_qr_eval_question"),
    )


class QRProcessingJob(db.Model):
    __tablename__ = "qr_processing_job"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status = db.Column(db.String(40), nullable=False, server_default="queued")
    attempt_count = db.Column(db.Integer, nullable=False, server_default="0")
    last_error = db.Column(db.Text)
    enqueued_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = db.Column(db.DateTime(timezone=True))
    finished_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QRDomainResult(db.Model):
    __tablename__ = "qr_domain_result"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain = db.Column(db.String(40), nullable=False)
    model_name = db.Column(db.String(120), nullable=False)
    model_version = db.Column(db.String(120), nullable=False)
    model_status = db.Column(db.String(120), nullable=False)
    probability = db.Column(db.Numeric(8, 6), nullable=False)
    threshold_used = db.Column(db.Numeric(8, 6), nullable=False)
    risk_band = db.Column(db.String(40), nullable=False)
    confidence_level = db.Column(db.String(40), nullable=False)
    evidence_level = db.Column(db.String(40), nullable=False)
    uncertainty_flag = db.Column(db.Boolean, nullable=False, server_default="false")
    abstention_flag = db.Column(db.Boolean, nullable=False, server_default="false")
    recommendation_text = db.Column(db.Text, nullable=False)
    explanation_short = db.Column(db.Text, nullable=False)
    contributors_json = db.Column(db.JSON)
    caveats_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("evaluation_id", "domain", name="uq_qr_eval_domain"),
    )


class QRNotification(db.Model):
    __tablename__ = "qr_notification"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False, index=True)
    evaluation_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notification_type = db.Column(db.String(60), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    payload_json = db.Column(db.JSON)
    is_read = db.Column(db.Boolean, nullable=False, server_default="false")
    read_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QRExportLog(db.Model):
    __tablename__ = "qr_export_log"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("qr_evaluation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    export_mode = db.Column(db.String(40), nullable=False)
    export_format = db.Column(db.String(40), nullable=False, server_default="json")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

# ==========================
# Questionnaire Backend v2
# ==========================


class QuestionnaireDefinition(db.Model):
    __tablename__ = "questionnaire_definitions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = db.Column(db.String(128), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QuestionnaireVersion(db.Model):
    __tablename__ = "questionnaire_versions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    definition_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_definitions.id", ondelete="CASCADE"), nullable=False
    )
    version_label = db.Column(db.String(64), nullable=False)
    source_folder = db.Column(db.String(512))
    source_master_csv = db.Column(db.String(512))
    source_visible_csv = db.Column(db.String(512))
    source_scales_csv = db.Column(db.String(512))
    source_preview_md = db.Column(db.String(512))
    source_pdf = db.Column(db.String(512))
    source_audit_md = db.Column(db.String(512))
    questionnaire_version_final = db.Column(db.String(128))
    scales_version_label = db.Column(db.String(128))
    metadata_json = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, nullable=False, server_default="false")
    published_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("definition_id", "version_label", name="uq_questionnaire_definition_version"),
    )


class QuestionnaireSection(db.Model):
    __tablename__ = "questionnaire_sections"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"), nullable=False
    )
    section_key = db.Column(db.String(160), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    position = db.Column(db.Integer, nullable=False)
    is_visible = db.Column(db.Boolean, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("version_id", "section_key", name="uq_questionnaire_version_section"),
    )


class QuestionnaireScale(db.Model):
    __tablename__ = "questionnaire_scales"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"), nullable=False
    )
    scale_id = db.Column(db.String(120), nullable=False)
    scale_name = db.Column(db.String(255), nullable=False)
    response_type = db.Column(db.String(64), nullable=False)
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    unit = db.Column(db.String(120))
    scale_guidance = db.Column(db.Text)
    options_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("version_id", "scale_id", name="uq_questionnaire_version_scale"),
    )


class QuestionnaireScaleOption(db.Model):
    __tablename__ = "questionnaire_scale_options"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scale_ref_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_scales.id", ondelete="CASCADE"), nullable=False
    )
    option_value = db.Column(db.String(120), nullable=False)
    option_label = db.Column(db.String(255), nullable=False)
    position = db.Column(db.Integer, nullable=False, server_default="1")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("scale_ref_id", "option_value", name="uq_questionnaire_scale_option_value"),
    )


class QuestionnaireQuestion(db.Model):
    __tablename__ = "questionnaire_questions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"), nullable=False
    )
    section_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_sections.id", ondelete="SET NULL"))
    question_code = db.Column(db.String(120), nullable=False)
    feature_key = db.Column(db.String(160), nullable=False, index=True)
    canonical_question_code = db.Column(db.String(120))
    question_text_primary = db.Column(db.Text)
    caregiver_question = db.Column(db.Text)
    psychologist_question = db.Column(db.Text)
    help_text = db.Column(db.Text)
    layer = db.Column(db.String(80))
    domain = db.Column(db.String(80), nullable=False, server_default="general")
    domains_final = db.Column(db.String(255))
    module = db.Column(db.String(120))
    criterion_ref = db.Column(db.String(120))
    instrument_or_source = db.Column(db.String(255))
    feature_type = db.Column(db.String(120))
    feature_role = db.Column(db.String(120))
    respondent_expected = db.Column(db.String(120))
    administered_by = db.Column(db.String(120))
    response_type = db.Column(db.String(64), nullable=False)
    scale_id = db.Column(db.String(120))
    response_options_json = db.Column(db.JSON)
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    unit = db.Column(db.String(80))
    visible_question = db.Column(db.Boolean, nullable=False, server_default="true")
    generated_input = db.Column(db.Boolean, nullable=False, server_default="false")
    is_internal_input = db.Column(db.Boolean, nullable=False, server_default="false")
    is_transparent_derived = db.Column(db.Boolean, nullable=False, server_default="false")
    requires_internal_scoring = db.Column(db.Boolean, nullable=False, server_default="false")
    requires_exact_item_wording = db.Column(db.Boolean, nullable=False, server_default="false")
    requires_clinician_administration = db.Column(db.Boolean, nullable=False, server_default="false")
    requires_child_self_report = db.Column(db.Boolean, nullable=False, server_default="false")
    display_order = db.Column(db.Integer, nullable=False, server_default="0")
    question_audit_status = db.Column(db.String(80))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("version_id", "question_code", name="uq_questionnaire_version_question_code"),
    )


class QuestionnaireQuestionMode(db.Model):
    __tablename__ = "questionnaire_question_modes"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), nullable=False
    )
    mode_key = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(40), nullable=False)
    delivery_mode = db.Column(db.String(40), nullable=False)
    is_included = db.Column(db.Boolean, nullable=False, server_default="true")
    priority_rank = db.Column(db.Float)
    priority_bucket = db.Column(db.String(40))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("question_id", "mode_key", name="uq_question_mode"),
    )


class QuestionnaireInternalInput(db.Model):
    __tablename__ = "questionnaire_internal_inputs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"), nullable=False
    )
    feature_key = db.Column(db.String(160), nullable=False)
    source_question_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_questions.id", ondelete="SET NULL"))
    derived_from_features = db.Column(db.JSON)
    internal_scoring_formula_summary = db.Column(db.Text)
    storage_type = db.Column(db.String(64), nullable=False, server_default="numeric")
    is_required = db.Column(db.Boolean, nullable=False, server_default="true")
    requires_internal_scoring = db.Column(db.Boolean, nullable=False, server_default="false")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("version_id", "feature_key", name="uq_questionnaire_internal_input_feature"),
    )


class QuestionnaireRepeatMapping(db.Model):
    __tablename__ = "questionnaire_repeat_mapping"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_versions.id", ondelete="CASCADE"), nullable=False
    )
    repeated_question_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), nullable=False
    )
    canonical_question_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), nullable=False
    )
    reuse_answer = db.Column(db.Boolean, nullable=False, server_default="true")
    mapping_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("version_id", "repeated_question_id", name="uq_questionnaire_repeat_question"),
    )


class ModelRegistry(db.Model):
    __tablename__ = "model_registry"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_key = db.Column(db.String(255), nullable=False, unique=True, index=True)
    domain = db.Column(db.String(64), nullable=False, index=True)
    mode_key = db.Column(db.String(64), nullable=False, index=True)
    role = db.Column(db.String(40), nullable=False, index=True)
    source_line = db.Column(db.String(120))
    source_campaign = db.Column(db.String(120))
    model_family = db.Column(db.String(120))
    feature_set_id = db.Column(db.String(160))
    config_id = db.Column(db.String(160))
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_to = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ModelVersion(db.Model):
    __tablename__ = "model_versions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_registry_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_version_tag = db.Column(db.String(128), nullable=False)
    artifact_path = db.Column(db.String(512))
    fallback_artifact_path = db.Column(db.String(512))
    checksum = db.Column(db.String(128))
    calibration = db.Column(db.String(120))
    threshold_policy = db.Column(db.String(120))
    threshold = db.Column(db.Float)
    seed = db.Column(db.String(40))
    n_features = db.Column(db.Integer)
    metadata_json = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("model_registry_id", "model_version_tag", name="uq_model_registry_version_tag"),
    )

class ModelModeDomainActivation(db.Model):
    __tablename__ = "model_mode_domain_activation"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = db.Column(db.String(64), nullable=False, index=True)
    mode_key = db.Column(db.String(64), nullable=False, index=True)
    role = db.Column(db.String(40), nullable=False, index=True)
    model_registry_id = db.Column(UUID(as_uuid=True), db.ForeignKey("model_registry.id", ondelete="RESTRICT"), nullable=False)
    model_version_id = db.Column(UUID(as_uuid=True), db.ForeignKey("model_versions.id", ondelete="RESTRICT"), nullable=False)
    active_flag = db.Column(db.Boolean, nullable=False, server_default="true")
    source_campaign = db.Column(db.String(120))
    valid_from = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_to = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint(
            "domain",
            "mode_key",
            "role",
            "active_flag",
            name="uq_model_mode_domain_active",
        ),
    )


class ModelMetricsSnapshot(db.Model):
    __tablename__ = "model_metrics_snapshot"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    precision = db.Column(db.Float)
    recall = db.Column(db.Float)
    specificity = db.Column(db.Float)
    balanced_accuracy = db.Column(db.Float)
    f1 = db.Column(db.Float)
    roc_auc = db.Column(db.Float)
    pr_auc = db.Column(db.Float)
    brier = db.Column(db.Float)
    overfit_flag = db.Column(db.String(32))
    generalization_flag = db.Column(db.String(32))
    dataset_ease_flag = db.Column(db.String(32))
    quality_label = db.Column(db.String(64))
    metrics_json = db.Column(db.JSON)
    captured_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class ModelArtifactRegistry(db.Model):
    __tablename__ = "model_artifact_registry"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_kind = db.Column(db.String(64), nullable=False)
    artifact_locator = db.Column(db.String(512), nullable=False)
    checksum = db.Column(db.String(128))
    is_available = db.Column(db.Boolean, nullable=False, server_default="true")
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("model_version_id", "artifact_kind", name="uq_model_version_artifact_kind"),
    )


class ModelConfidenceRegistry(db.Model):
    __tablename__ = "model_confidence_registry"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activation_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("model_mode_domain_activation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    confidence_pct = db.Column(db.Float)
    confidence_band = db.Column(db.String(64))
    operational_class = db.Column(db.String(120))
    recommended_for_default_use = db.Column(db.Boolean, nullable=False, server_default="false")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ModelOperationalCaveat(db.Model):
    __tablename__ = "model_operational_caveats"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activation_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("model_mode_domain_activation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    caveat = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(40), nullable=False, server_default="medium")
    is_blocking = db.Column(db.Boolean, nullable=False, server_default="false")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QuestionnaireSession(db.Model):
    __tablename__ = "questionnaire_sessions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    questionnaire_public_id = db.Column(db.String(40), nullable=False, unique=True, index=True)
    version_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    owner_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False, index=True)
    respondent_role = db.Column(db.String(40), nullable=False)
    mode = db.Column(db.String(40), nullable=False)
    mode_key = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(40), nullable=False, server_default="draft", index=True)
    progress_pct = db.Column(db.Float, nullable=False, server_default="0")
    completion_quality_score = db.Column(db.Float)
    missingness_score = db.Column(db.Float)
    inconsistency_flags_json = db.Column(db.JSON)
    model_pipeline_version = db.Column(db.String(128))
    questionnaire_version_label = db.Column(db.String(128))
    scales_version_label = db.Column(db.String(128))
    metadata_json = db.Column(db.JSON)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    submitted_at = db.Column(db.DateTime(timezone=True))
    processed_at = db.Column(db.DateTime(timezone=True))
    failed_at = db.Column(db.DateTime(timezone=True))
    archived_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QuestionnaireSessionItem(db.Model):
    __tablename__ = "questionnaire_session_items"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_sections.id", ondelete="SET NULL"))
    question_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), nullable=False)
    page_number = db.Column(db.Integer, nullable=False, server_default="1")
    display_order = db.Column(db.Integer, nullable=False, server_default="0")
    is_visible = db.Column(db.Boolean, nullable=False, server_default="true")
    is_required = db.Column(db.Boolean, nullable=False, server_default="true")
    answered = db.Column(db.Boolean, nullable=False, server_default="false")
    answered_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("session_id", "question_id", name="uq_questionnaire_session_question"),
    )


class QuestionnaireSessionAnswer(db.Model):
    __tablename__ = "questionnaire_session_answers"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_questions.id", ondelete="CASCADE"), nullable=False)
    canonical_question_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_questions.id", ondelete="SET NULL"))
    answer_raw = db.Column(db.JSON, nullable=False)
    answer_normalized = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(40), nullable=False, server_default="user")
    answered_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    is_final = db.Column(db.Boolean, nullable=False, server_default="false")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("session_id", "question_id", name="uq_questionnaire_session_answer"),
    )


class QuestionnaireSessionInternalFeature(db.Model):
    __tablename__ = "questionnaire_session_internal_features"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_key = db.Column(db.String(160), nullable=False)
    feature_value_numeric = db.Column(db.Float)
    feature_value_text = db.Column(db.Text)
    source_type = db.Column(db.String(40), nullable=False, server_default="direct")
    source_question_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_questions.id", ondelete="SET NULL"))
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("session_id", "feature_key", name="uq_session_feature_key"),
    )


class QuestionnaireSessionResult(db.Model):
    __tablename__ = "questionnaire_session_results"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    summary_text = db.Column(db.Text, nullable=False)
    operational_recommendation = db.Column(db.Text, nullable=False)
    completion_quality_score = db.Column(db.Float)
    missingness_score = db.Column(db.Float)
    inconsistency_flags_json = db.Column(db.JSON)
    needs_professional_review = db.Column(db.Boolean, nullable=False, server_default="false")
    runtime_ms = db.Column(db.Float)
    model_bundle_version = db.Column(db.String(128))
    questionnaire_version_label = db.Column(db.String(128))
    scales_version_label = db.Column(db.String(128))
    metadata_json = db.Column(db.JSON)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QuestionnaireSessionResultDomain(db.Model):
    __tablename__ = "questionnaire_session_result_domains"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_session_results.id", ondelete="CASCADE"), nullable=False
    )
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain = db.Column(db.String(64), nullable=False, index=True)
    probability = db.Column(db.Float, nullable=False)
    alert_level = db.Column(db.String(40), nullable=False)
    confidence_pct = db.Column(db.Float)
    confidence_band = db.Column(db.String(64))
    model_id = db.Column(db.String(255), nullable=False)
    model_version = db.Column(db.String(128))
    mode = db.Column(db.String(64), nullable=False)
    operational_class = db.Column(db.String(120))
    operational_caveat = db.Column(db.Text)
    result_summary = db.Column(db.Text, nullable=False)
    needs_professional_review = db.Column(db.Boolean, nullable=False, server_default="false")
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("result_id", "domain", name="uq_result_domain"),
    )

class QuestionnaireSessionResultComorbidity(db.Model):
    __tablename__ = "questionnaire_session_result_comorbidity"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_session_results.id", ondelete="CASCADE"), nullable=False
    )
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    coexistence_key = db.Column(db.String(120), nullable=False)
    domains_json = db.Column(db.JSON, nullable=False)
    combined_risk_score = db.Column(db.Float, nullable=False)
    coexistence_level = db.Column(db.String(40), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QuestionnaireSessionPdfExport(db.Model):
    __tablename__ = "questionnaire_session_pdf_exports"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path = db.Column(db.String(512), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(40), nullable=False, server_default="generated")
    generated_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class QuestionnaireSessionAccessLink(db.Model):
    __tablename__ = "questionnaire_session_access_links"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    access_type = db.Column(db.String(40), nullable=False)
    actor_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    share_code_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_share_codes.id", ondelete="SET NULL"))
    access_grant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_access_grants.id", ondelete="SET NULL"))
    ip_address = db.Column(db.String(80))
    user_agent = db.Column(db.String(255))
    success = db.Column(db.Boolean, nullable=False, server_default="true")
    notes = db.Column(db.Text)
    accessed_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class QuestionnaireTag(db.Model):
    __tablename__ = "questionnaire_tags"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    color = db.Column(db.String(16), nullable=False, server_default="#5B6C7D")
    visibility = db.Column(db.String(40), nullable=False, server_default="private")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("owner_user_id", "name", name="uq_questionnaire_tag_owner_name"),
    )


class QuestionnaireSessionTag(db.Model):
    __tablename__ = "questionnaire_session_tags"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False
    )
    tag_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_tags.id", ondelete="CASCADE"), nullable=False)
    assigned_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        db.UniqueConstraint("session_id", "tag_id", "assigned_by_user_id", name="uq_questionnaire_session_tag"),
    )


class QuestionnaireAccessGrant(db.Model):
    __tablename__ = "questionnaire_access_grants"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    grantee_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False, index=True)
    grant_type = db.Column(db.String(40), nullable=False, server_default="manual")
    can_view = db.Column(db.Boolean, nullable=False, server_default="true")
    can_tag = db.Column(db.Boolean, nullable=False, server_default="true")
    can_download_pdf = db.Column(db.Boolean, nullable=False, server_default="true")
    expires_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        db.UniqueConstraint("session_id", "grantee_user_id", name="uq_questionnaire_access_grantee"),
    )


class QuestionnaireShareCode(db.Model):
    __tablename__ = "questionnaire_share_codes"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash = db.Column(db.String(255), nullable=False)
    code_hint = db.Column(db.String(16))
    created_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, server_default="true")
    expires_at = db.Column(db.DateTime(timezone=True))
    max_uses = db.Column(db.Integer)
    used_count = db.Column(db.Integer, nullable=False, server_default="0")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DashboardAggregate(db.Model):
    __tablename__ = "dashboard_aggregates"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_key = db.Column(db.String(120), nullable=False, index=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    value_numeric = db.Column(db.Float)
    value_json = db.Column(db.JSON)
    computed_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        db.UniqueConstraint("aggregate_key", "period_start", "period_end", name="uq_dashboard_aggregate_period"),
    )


class ReportJob(db.Model):
    __tablename__ = "report_jobs"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = db.Column(db.String(120), nullable=False, index=True)
    requested_by_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False)
    status = db.Column(db.String(40), nullable=False, server_default="queued")
    params_json = db.Column(db.JSON)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = db.Column(db.DateTime(timezone=True))
    finished_at = db.Column(db.DateTime(timezone=True))


class GeneratedReport(db.Model):
    __tablename__ = "generated_reports"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_job_id = db.Column(UUID(as_uuid=True), db.ForeignKey("report_jobs.id", ondelete="SET NULL"))
    report_type = db.Column(db.String(120), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_format = db.Column(db.String(40), nullable=False, server_default="pdf")
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class ServiceHealthSnapshot(db.Model):
    __tablename__ = "service_health_snapshots"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    api_uptime_seconds = db.Column(db.Float)
    requests_total = db.Column(db.Integer)
    error_rate = db.Column(db.Float)
    avg_latency_ms = db.Column(db.Float)
    db_ready = db.Column(db.Boolean)
    queue_depth = db.Column(db.Integer)
    payload_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class ModelMonitoringSnapshot(db.Model):
    __tablename__ = "model_monitoring_snapshots"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    domain = db.Column(db.String(64), nullable=False, index=True)
    mode_key = db.Column(db.String(64), nullable=False, index=True)
    samples_count = db.Column(db.Integer)
    mean_probability = db.Column(db.Float)
    alert_rate = db.Column(db.Float)
    drift_score = db.Column(db.Float)
    calibration_error = db.Column(db.Float)
    equity_gap = db.Column(db.Float)
    payload_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class QuestionnaireAuditEvent(db.Model):
    __tablename__ = "questionnaire_audit_events"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="SET NULL"))
    actor_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    event_type = db.Column(db.String(120), nullable=False, index=True)
    payload_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class ProblemReport(db.Model):
    __tablename__ = "problem_reports"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_code = db.Column(db.String(24), nullable=False, unique=True, index=True)
    reporter_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"), nullable=False, index=True)
    reporter_role = db.Column(db.String(64), nullable=False, index=True)
    issue_type = db.Column(db.String(80), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    source_module = db.Column(db.String(120))
    source_path = db.Column(db.String(255))
    related_questionnaire_session_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("questionnaire_sessions.id", ondelete="SET NULL")
    )
    related_questionnaire_history_id = db.Column(db.String(64))
    status = db.Column(db.String(40), nullable=False, server_default="open", index=True)
    admin_notes = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime(timezone=True))
    attachment_count = db.Column(db.Integer, nullable=False, server_default="0")
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProblemReportAttachment(db.Model):
    __tablename__ = "problem_report_attachments"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("problem_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_kind = db.Column(db.String(40), nullable=False, server_default="local")
    file_path = db.Column(db.String(512), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(120))
    size_bytes = db.Column(db.BigInteger, nullable=False)
    checksum_sha256 = db.Column(db.String(64), nullable=False)
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class ProblemReportAuditEvent(db.Model):
    __tablename__ = "problem_report_audit_events"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("problem_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("app_user.id"))
    event_type = db.Column(db.String(120), nullable=False, index=True)
    payload_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
