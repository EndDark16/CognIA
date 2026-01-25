# api/schemas/questionnaire_schema.py

from marshmallow import Schema, fields, validate


class QuestionnaireCreateSchema(Schema):
    name = fields.String(required=True)
    version = fields.String(required=True)
    description = fields.String(allow_none=True)


class QuestionnaireCloneSchema(Schema):
    version = fields.String(required=True)
    name = fields.String(allow_none=True)
    description = fields.String(allow_none=True)


class QuestionCreateSchema(Schema):
    code = fields.String(required=True)
    text = fields.String(required=True)
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
    position = fields.Integer(allow_none=True)
    response_min = fields.Float(allow_none=True)
    response_max = fields.Float(allow_none=True)
    response_step = fields.Float(allow_none=True)
    response_options = fields.List(fields.Raw(), allow_none=True)
