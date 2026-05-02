from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema


ISSUE_TYPES = (
    "bug",
    "ui_issue",
    "data_issue",
    "performance",
    "questionnaire",
    "model_result",
    "other",
)

REPORT_STATUSES = (
    "open",
    "triaged",
    "in_progress",
    "resolved",
    "rejected",
)


class BaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class ProblemReportCreateSchema(BaseSchema):
    issue_type = fields.String(required=True, validate=validate.OneOf(ISSUE_TYPES))
    description = fields.String(required=True, validate=validate.Length(min=10, max=4000))
    source_module = fields.String(required=False, validate=validate.Length(min=1, max=120))
    source_path = fields.String(required=False, validate=validate.Length(min=1, max=255))
    related_questionnaire_session_id = fields.UUID(required=False)
    related_questionnaire_history_id = fields.String(required=False, validate=validate.Length(min=1, max=64))
    metadata = fields.Dict(required=False)


class ProblemReportListQuerySchema(BaseSchema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
    status = fields.String(required=False, validate=validate.OneOf(REPORT_STATUSES))
    issue_type = fields.String(required=False, validate=validate.OneOf(ISSUE_TYPES))
    reporter_role = fields.String(required=False, validate=validate.Length(min=1, max=64))
    q = fields.String(required=False, validate=validate.Length(min=1, max=200))
    from_date = fields.DateTime(required=False)
    to_date = fields.DateTime(required=False)
    sort = fields.String(
        load_default="created_at",
        validate=validate.OneOf(["created_at", "updated_at", "resolved_at", "status", "issue_type"]),
    )
    order = fields.String(load_default="desc", validate=validate.OneOf(["asc", "desc"]))

    @validates_schema
    def validate_range(self, data, **kwargs):
        from_date = data.get("from_date")
        to_date = data.get("to_date")
        if from_date and to_date and from_date > to_date:
            raise ValidationError("from_date must be before or equal to to_date", field_name="from_date")


class ProblemReportUpdateSchema(BaseSchema):
    status = fields.String(required=False, validate=validate.OneOf(REPORT_STATUSES))
    admin_notes = fields.String(required=False, validate=validate.Length(min=1, max=5000))

    @validates_schema
    def validate_any_field(self, data, **kwargs):
        if not data:
            raise ValidationError("At least one field must be provided")
