# api/schemas/questionnaire_schema.py

from marshmallow import Schema, fields, validate

_NAME_MAX = 120
_VERSION_MAX = 32
_CODE_MAX = 64
_VERSION_RE = r"^[A-Za-z0-9._-]{1,32}$"
_CODE_RE = r"^[A-Za-z0-9_-]{2,64}$"


class QuestionnaireCreateSchema(Schema):
    name = fields.String(required=True, validate=[validate.Length(min=3, max=_NAME_MAX), validate.Regexp(r"\S")])
    version = fields.String(required=True, validate=[validate.Length(max=_VERSION_MAX), validate.Regexp(_VERSION_RE)])
    description = fields.String(allow_none=True)


class QuestionnaireCloneSchema(Schema):
    version = fields.String(required=True, validate=[validate.Length(max=_VERSION_MAX), validate.Regexp(_VERSION_RE)])
    name = fields.String(allow_none=True, validate=[validate.Length(min=3, max=_NAME_MAX), validate.Regexp(r"\S")])
    description = fields.String(allow_none=True)


class QuestionCreateSchema(Schema):
    code = fields.String(required=True, validate=[validate.Length(max=_CODE_MAX), validate.Regexp(_CODE_RE)])
    text = fields.String(required=True, validate=validate.Length(min=3, max=500))
    response_type = fields.String(
        required=True,
        validate=validate.OneOf(
            [
                "likert_0_4",
                "likert_1_5",
                "boolean",
                "frequency_0_3",
                "intensity_0_10",
                "count",
                "ordinal",
                "text_context",
            ]
        ),
    )
    disorder_id = fields.UUID(allow_none=True)
    disorder_ids = fields.List(fields.UUID(), allow_none=True)
    position = fields.Integer(allow_none=True, validate=validate.Range(min=0))
    response_min = fields.Float(allow_none=True)
    response_max = fields.Float(allow_none=True)
    response_step = fields.Float(allow_none=True)
    response_options = fields.List(fields.Raw(), allow_none=True)
