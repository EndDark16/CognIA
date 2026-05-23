from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema


MODES = ("short", "medium", "complete")
ROLES = ("guardian", "psychologist")
ALERT_LEVELS = ("low", "moderate", "elevated", "high", "critical_review")


class BaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class SessionCreateSchema(BaseSchema):
    mode = fields.String(required=True, validate=validate.OneOf(MODES))
    role = fields.String(required=True, validate=validate.OneOf(ROLES))
    child_age_years = fields.Integer(required=False, validate=validate.Range(min=6, max=11))
    child_sex_assigned_at_birth = fields.String(required=False, validate=validate.Length(min=1, max=40))
    case_id = fields.UUID(required=False)
    case_public_id = fields.String(required=False, validate=validate.Length(min=3, max=40))
    case_label = fields.String(required=False, validate=validate.Length(min=1, max=160))
    metadata = fields.Dict(required=False)


class SessionAnswerItemSchema(BaseSchema):
    question_id = fields.UUID(required=False)
    question_code = fields.String(required=False, validate=validate.Length(min=1, max=80))
    answer = fields.Raw(required=True)

    @validates_schema
    def validate_identifier(self, data, **kwargs):
        if data.get("question_id") is None and not str(data.get("question_code") or "").strip():
            raise ValidationError("question_id_or_question_code_required")


class SessionAnswersPatchSchema(BaseSchema):
    answers = fields.List(fields.Nested(SessionAnswerItemSchema), required=True, validate=validate.Length(min=1))
    mark_final = fields.Boolean(load_default=False)
    include_answers = fields.Boolean(load_default=False)


class SessionPageQuerySchema(BaseSchema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class ShareCreateSchema(BaseSchema):
    expires_in_hours = fields.Integer(required=False, validate=validate.Range(min=1, max=24 * 365))
    max_uses = fields.Integer(required=False, validate=validate.Range(min=1, max=10000))
    grantee_user_id = fields.UUID(required=False)
    grant_can_tag = fields.Boolean(load_default=True)
    grant_can_download_pdf = fields.Boolean(load_default=True)
    share_scope = fields.String(required=False, validate=validate.OneOf(["session", "case"]))


class TagAssignSchema(BaseSchema):
    tag = fields.String(required=True, validate=validate.Length(min=1, max=120))
    color = fields.String(required=False, validate=validate.Length(min=4, max=16))
    visibility = fields.String(required=False, validate=validate.OneOf(["private", "shared"]))


class DashboardQuerySchema(BaseSchema):
    months = fields.Integer(load_default=12, validate=validate.Range(min=1, max=120))
    date_from = fields.Date(required=False)
    date_to = fields.Date(required=False)

    @validates_schema
    def validate_period(self, data, **kwargs):
        start = data.get("date_from")
        end = data.get("date_to")
        if start and end and start > end:
            raise ValidationError("invalid_period_range")


class GuardianDashboardQuerySchema(DashboardQuerySchema):
    case_id = fields.UUID(required=False)
    case_public_id = fields.String(required=False, validate=validate.Length(min=3, max=40))


class PsychologistDashboardQuerySchema(BaseSchema):
    q = fields.String(required=False, validate=validate.Length(min=1, max=160))
    case_public_id = fields.String(required=False, validate=validate.Length(min=3, max=40))
    date_from = fields.Date(required=False)
    date_to = fields.Date(required=False)
    domain = fields.String(required=False, validate=validate.Length(min=1, max=64))
    alert_level = fields.String(required=False, validate=validate.OneOf(ALERT_LEVELS))
    review_status = fields.String(
        required=False,
        validate=validate.OneOf(["pending", "in_review", "reviewed", "orientation_recommended", "closed"]),
    )
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))

    @validates_schema
    def validate_period(self, data, **kwargs):
        start = data.get("date_from")
        end = data.get("date_to")
        if start and end and start > end:
            raise ValidationError("invalid_period_range")


class PsychologistSearchQuerySchema(BaseSchema):
    q = fields.String(required=False, validate=validate.Length(min=1, max=160))
    location = fields.String(required=False, validate=validate.Length(min=1, max=160))
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class CaseCreateSchema(BaseSchema):
    private_label = fields.String(required=True, validate=validate.Length(min=1, max=160))
    metadata = fields.Dict(required=False)


class CaseUpdateSchema(BaseSchema):
    private_label = fields.String(required=False, validate=validate.Length(min=1, max=160))
    status = fields.String(required=False, validate=validate.OneOf(["active", "archived"]))


class CaseListQuerySchema(BaseSchema):
    status = fields.String(required=False, validate=validate.OneOf(["active", "archived"]))
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class ProfessionalReviewCreateSchema(BaseSchema):
    review_status = fields.String(
        required=True,
        validate=validate.OneOf(["pending", "in_review", "reviewed", "orientation_recommended", "closed"]),
    )
    initial_concept = fields.String(required=True, validate=validate.Length(min=1, max=4000))
    recommendation = fields.String(required=False, validate=validate.Length(max=4000))
    visible_to_guardian = fields.Boolean(load_default=True)


class ProfessionalReviewUpdateSchema(BaseSchema):
    review_status = fields.String(
        required=False,
        validate=validate.OneOf(["pending", "in_review", "reviewed", "orientation_recommended", "closed"]),
    )
    initial_concept = fields.String(required=False, validate=validate.Length(min=1, max=4000))
    recommendation = fields.String(required=False, validate=validate.Length(max=4000))
    visible_to_guardian = fields.Boolean(required=False)


class ReportRequestSchema(BaseSchema):
    report_type = fields.String(
        required=True,
        validate=validate.OneOf(
            [
                "executive_monthly",
                "adoption_history",
                "executive_summary",
                "user_growth",
                "questionnaire_volume",
                "funnel",
                "retention",
                "productivity",
                "questionnaire_quality",
                "data_quality",
                "api_health",
                "model_monitoring",
                "drift",
                "equity",
                "human_review",
                "operational_productivity",
                "security_compliance",
                "traceability_audit",
            ]
        ),
    )
    months = fields.Integer(load_default=12, validate=validate.Range(min=1, max=120))
    date_from = fields.Date(required=False)
    date_to = fields.Date(required=False)
    granularity = fields.String(required=False, load_default="month", validate=validate.OneOf(["day", "week", "month"]))
    format = fields.String(required=False, load_default="pdf", validate=validate.OneOf(["pdf"]))
    filters = fields.Dict(required=False, load_default=dict)

    @validates_schema
    def validate_period(self, data, **kwargs):
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError("date_from_must_be_before_or_equal_date_to")


class SessionSubmitSchema(BaseSchema):
    force_reprocess = fields.Boolean(load_default=False)


class SessionFilterSchema(BaseSchema):
    status = fields.String(
        required=False,
        validate=validate.OneOf(["draft", "in_progress", "submitted", "processed", "failed", "archived"]),
    )
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class SharedAccessSchema(BaseSchema):
    questionnaire_id = fields.String(required=True, validate=validate.Length(min=6, max=64))
    share_code = fields.String(required=True, validate=validate.Length(min=6, max=64))


class DomainResultSchema(BaseSchema):
    domain = fields.String(required=True)
    probability = fields.Float(required=True, validate=validate.Range(min=0, max=1))
    alert_level = fields.String(required=True, validate=validate.OneOf(ALERT_LEVELS))
    confidence_pct = fields.Float(required=True, validate=validate.Range(min=0, max=100))
    confidence_band = fields.String(required=True)
    model_id = fields.String(required=True)
    model_version = fields.String(required=False)
    mode = fields.String(required=True)
    operational_caveat = fields.String(required=False)
    result_summary = fields.String(required=True)
    needs_professional_review = fields.Boolean(required=True)

    @validates_schema
    def validate_probability_vs_confidence(self, data, **kwargs):
        probability = data.get("probability")
        confidence = data.get("confidence_pct")
        if probability is None or confidence is None:
            return
        if abs((probability * 100.0) - confidence) > 0.11:
            raise ValidationError("confidence_pct must be consistent with probability")
