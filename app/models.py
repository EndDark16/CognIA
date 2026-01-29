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
    failed_login_attempts = db.Column(db.Integer, nullable=False, server_default="0")
    last_failed_login_at = db.Column(db.DateTime(timezone=True))
    login_locked_until = db.Column(db.DateTime(timezone=True))
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
