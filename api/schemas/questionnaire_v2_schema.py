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
    metadata = fields.Dict(required=False)


class SessionAnswerItemSchema(BaseSchema):
    question_id = fields.UUID(required=True)
    answer = fields.Raw(required=True)


class SessionAnswersPatchSchema(BaseSchema):
    answers = fields.List(fields.Nested(SessionAnswerItemSchema), required=True, validate=validate.Length(min=1))
    mark_final = fields.Boolean(load_default=False)


class SessionPageQuerySchema(BaseSchema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class ShareCreateSchema(BaseSchema):
    expires_in_hours = fields.Integer(required=False, validate=validate.Range(min=1, max=24 * 365))
    max_uses = fields.Integer(required=False, validate=validate.Range(min=1, max=10000))
    grantee_user_id = fields.UUID(required=False)
    grant_can_tag = fields.Boolean(load_default=True)
    grant_can_download_pdf = fields.Boolean(load_default=True)


class TagAssignSchema(BaseSchema):
    tag = fields.String(required=True, validate=validate.Length(min=1, max=120))
    color = fields.String(required=False, validate=validate.Length(min=4, max=16))
    visibility = fields.String(required=False, validate=validate.OneOf(["private", "shared"]))


class DashboardQuerySchema(BaseSchema):
    months = fields.Integer(load_default=12, validate=validate.Range(min=1, max=120))


class ReportRequestSchema(BaseSchema):
    report_type = fields.String(
        required=True,
        validate=validate.OneOf(
            [
                "executive_monthly",
                "adoption_history",
                "model_monitoring",
                "operational_productivity",
                "security_compliance",
                "traceability_audit",
            ]
        ),
    )
    months = fields.Integer(load_default=12, validate=validate.Range(min=1, max=120))


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
