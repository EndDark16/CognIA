from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class UserListQuerySchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class UserCreateSchema(Schema):
    username = fields.String(required=True)
    email = fields.String(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8, max=128))
    full_name = fields.String(allow_none=True)
    user_type = fields.String(required=True)
    professional_card_number = fields.String(allow_none=True)
    roles = fields.List(fields.String(), allow_none=True)
    is_active = fields.Boolean(load_default=True)


class UserUpdateSchema(Schema):
    email = fields.String(allow_none=True)
    password = fields.String(allow_none=True, validate=validate.Length(min=8, max=128))
    full_name = fields.String(allow_none=True)
    user_type = fields.String(allow_none=True)
    professional_card_number = fields.String(allow_none=True)
    roles = fields.List(fields.String(), allow_none=True)
    is_active = fields.Boolean(allow_none=True)

    @validates_schema
    def validate_has_any_field(self, data, **kwargs):
        if not data:
            raise ValidationError("At least one field must be provided")
