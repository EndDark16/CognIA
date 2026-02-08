# api/schemas/email_schema.py

from marshmallow import Schema, fields, validate


class EmailUnsubscribeSchema(Schema):
    token = fields.String(required=True, validate=validate.Length(min=10, max=512))
    reason = fields.String(required=False, validate=validate.Length(max=200))
