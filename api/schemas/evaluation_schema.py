# api/schemas/evaluation_schema.py

from marshmallow import Schema, fields, validate


class EvaluationResponseSchema(Schema):
    question_id = fields.UUID(required=True)
    value = fields.Raw(required=True)


class EvaluationCreateSchema(Schema):
    subject_id = fields.UUID(allow_none=True)
    age_at_evaluation = fields.Integer(required=True, validate=validate.Range(min=0))
    evaluation_date = fields.Date(required=True)
    status = fields.String(required=True)
    is_anonymous = fields.Boolean(load_default=True)
    context = fields.String(allow_none=True)
    raw_symptoms = fields.Dict(allow_none=True)
    processed_features = fields.Dict(allow_none=True)
    access_key = fields.String(allow_none=True)
    responses = fields.List(
        fields.Nested(EvaluationResponseSchema),
        required=True,
        validate=validate.Length(min=1),
    )
