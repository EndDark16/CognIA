from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema


ALLOWED_RESPONDENT_TYPES = ("caregiver", "psychologist")
ALLOWED_DISCLOSURE_TYPES = (
    "consent_pre",
    "disclaimer_pre",
    "disclaimer_result",
    "disclaimer_pdf",
)
ALLOWED_RESPONSE_TYPES = (
    "single_choice",
    "multi_choice",
    "boolean",
    "integer",
    "likert_single",
    "numeric_range",
    "consent/info_only",
)


class BaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class RuntimeAnswerItemSchema(BaseSchema):
    question_id = fields.UUID(required=True)
    value = fields.Raw(required=True)


class RuntimeCreateDraftSchema(BaseSchema):
    respondent_type = fields.String(
        load_default="caregiver",
        validate=validate.OneOf(ALLOWED_RESPONDENT_TYPES),
    )
    child_age_years = fields.Integer(
        required=True,
        validate=validate.Range(min=6, max=11),
    )
    child_sex_assigned_at_birth = fields.String(
        required=False,
        validate=validate.Length(min=1, max=32),
    )
    consent_accepted = fields.Boolean(load_default=False)
    is_waiting_live_result = fields.Boolean(load_default=True)
    answers = fields.List(
        fields.Nested(RuntimeAnswerItemSchema),
        load_default=list,
    )


class RuntimeSaveDraftSchema(BaseSchema):
    answers = fields.List(
        fields.Nested(RuntimeAnswerItemSchema),
        load_default=list,
    )
    consent_accepted = fields.Boolean(required=False)


class RuntimeValidateSectionSchema(BaseSchema):
    section_key = fields.String(required=True, validate=validate.Length(min=1, max=120))


class RuntimeSubmitSchema(BaseSchema):
    wait_live_result = fields.Boolean(load_default=True)


class RuntimeProfessionalAccessSchema(BaseSchema):
    reference_id = fields.String(required=True, validate=validate.Length(min=6, max=64))
    pin = fields.String(required=True, validate=validate.Length(min=4, max=32))


class RuntimeProfessionalTagSchema(BaseSchema):
    tag = fields.String(required=True, validate=validate.Length(min=1, max=64))


class RuntimeAdminTemplateCreateSchema(BaseSchema):
    slug = fields.String(
        required=True,
        validate=[
            validate.Length(min=3, max=120),
            validate.Regexp(r"^[a-z0-9][a-z0-9_-]*$"),
        ],
    )
    name = fields.String(required=True, validate=validate.Length(min=3, max=180))
    description = fields.String(required=False, validate=validate.Length(max=2000))
    is_active = fields.Boolean(load_default=True)


class RuntimeAdminVersionCreateSchema(BaseSchema):
    version_label = fields.String(required=True, validate=validate.Length(min=1, max=80))
    changelog = fields.String(required=False, validate=validate.Length(max=4000))
    clone_from_active = fields.Boolean(load_default=False)


class RuntimeAdminTemplateActiveSchema(BaseSchema):
    is_active = fields.Boolean(load_default=True)


class RuntimeAdminDisclosureSchema(BaseSchema):
    disclosure_type = fields.String(
        required=True,
        validate=validate.OneOf(ALLOWED_DISCLOSURE_TYPES),
    )
    version_label = fields.String(required=False, validate=validate.Length(min=1, max=40))
    title = fields.String(required=True, validate=validate.Length(min=1, max=300))
    content_markdown = fields.String(required=True, validate=validate.Length(min=1, max=20000))


class RuntimeAdminSectionSchema(BaseSchema):
    key = fields.String(
        required=True,
        validate=[
            validate.Length(min=1, max=120),
            validate.Regexp(r"^[a-z0-9][a-z0-9_-]*$"),
        ],
    )
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(required=False, validate=validate.Length(max=2000))
    position = fields.Integer(load_default=1, validate=validate.Range(min=1, max=2000))
    is_required = fields.Boolean(load_default=True)


class RuntimeAdminQuestionOptionSchema(BaseSchema):
    value = fields.String(required=True, validate=validate.Length(min=1, max=120))
    label = fields.String(required=True, validate=validate.Length(min=1, max=300))


class RuntimeAdminQuestionSchema(BaseSchema):
    key = fields.String(
        required=True,
        validate=[
            validate.Length(min=1, max=120),
            validate.Regexp(r"^[a-z0-9][a-z0-9_.-]*$"),
        ],
    )
    feature_key = fields.String(
        required=True,
        validate=[
            validate.Length(min=1, max=120),
            validate.Regexp(r"^[a-z0-9][a-z0-9_.-]*$"),
        ],
    )
    domain = fields.String(required=False, validate=validate.Length(min=1, max=80))
    prompt = fields.String(required=True, validate=validate.Length(min=1, max=1000))
    help_text = fields.String(required=False, validate=validate.Length(max=2000))
    response_type = fields.String(required=True, validate=validate.OneOf(ALLOWED_RESPONSE_TYPES))
    requiredness = fields.String(
        required=False,
        validate=validate.OneOf(["required", "optional"]),
    )
    position = fields.Integer(load_default=1, validate=validate.Range(min=1, max=5000))
    min_value = fields.Float(required=False)
    max_value = fields.Float(required=False)
    step_value = fields.Float(required=False, validate=validate.Range(min=0.000001))
    allowed_values = fields.Raw(required=False)
    visibility_rule = fields.Raw(required=False)
    is_active = fields.Boolean(load_default=True)
    options = fields.List(fields.Nested(RuntimeAdminQuestionOptionSchema), load_default=list)

    @validates_schema
    def validate_numeric_bounds(self, data, **kwargs):
        min_value = data.get("min_value")
        max_value = data.get("max_value")
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValidationError("min_value must be <= max_value", field_name="min_value")
