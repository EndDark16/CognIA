import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

db = SQLAlchemy()

# Modelos existentes reutilizados
class AppUser(db.Model):
    __tablename__ = 'app_user'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String, unique=True, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column("password_hash", db.String, nullable=False)
    full_name = db.Column(db.String)
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
