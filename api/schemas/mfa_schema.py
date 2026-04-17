from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class MFAConfirmSchema(Schema):
    code = fields.String(required=True, validate=validate.Length(min=6, max=12))


class MFADisableSchema(Schema):
    password = fields.String(required=True, validate=validate.Length(min=1, max=200))
    code = fields.String(load_default=None, validate=validate.Length(min=6, max=12))
    recovery_code = fields.String(load_default=None, validate=validate.Length(min=6, max=255))

    @validates_schema
    def validate_second_factor(self, data, **kwargs):
        has_code = bool(data.get("code"))
        has_recovery = bool(data.get("recovery_code"))
        if not has_code and not has_recovery:
            raise ValidationError("At least one of code or recovery_code is required")
        if has_code and has_recovery:
            raise ValidationError("Provide only one of code or recovery_code")
