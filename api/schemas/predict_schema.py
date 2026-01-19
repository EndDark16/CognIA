# api/schemas/predict_schema.py

from marshmallow import Schema, fields, validate

class PredictSchema(Schema):
    age = fields.Integer(required=True, validate=validate.Range(min=3, max=21))
    sex = fields.Integer(required=True, validate=validate.OneOf([0, 1]))  # 0=f, 1=m
    conners_inattention_score = fields.Float(required=True)
    conners_hyperactivity = fields.Float(required=True)
    cbcl_attention_score = fields.Float(required=True)
    sleep_problems = fields.Integer(required=True, validate=validate.OneOf([0, 1]))
