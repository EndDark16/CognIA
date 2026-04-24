from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class PaginationSchema(Schema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    page_size = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class UserListQuerySchema(PaginationSchema):
    q = fields.String(load_default=None)
    email = fields.String(load_default=None)
    username = fields.String(load_default=None)
    role = fields.String(load_default=None)
    user_type = fields.String(load_default=None)
    is_active = fields.Boolean(load_default=None)
    colpsic_verified = fields.Boolean(load_default=None)
    sort = fields.String(load_default=None)
    order = fields.String(load_default=None, validate=validate.OneOf(["asc", "desc"]))


class UserPatchSchema(Schema):
    is_active = fields.Boolean(load_default=None)
    roles = fields.List(fields.String(), load_default=None)
    user_type = fields.String(load_default=None)
    professional_card_number = fields.String(load_default=None)

    @validates_schema
    def validate_any_field(self, data, **kwargs):
        if not data:
            raise ValidationError("At least one field must be provided")


class RoleAssignSchema(Schema):
    roles = fields.List(fields.String(), required=True, validate=validate.Length(min=1))


class RoleCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=2, max=64))
    description = fields.String(load_default=None, validate=validate.Length(max=255))


class AuditLogQuerySchema(PaginationSchema):
    user_id = fields.String(load_default=None)
    action = fields.String(load_default=None)
    section = fields.String(load_default=None)
    from_date = fields.DateTime(load_default=None)
    to_date = fields.DateTime(load_default=None)
    sort = fields.String(load_default=None)
    order = fields.String(load_default=None, validate=validate.OneOf(["asc", "desc"]))


class QuestionnaireListQuerySchema(PaginationSchema):
    name = fields.String(load_default=None)
    version = fields.String(load_default=None)
    is_active = fields.Boolean(load_default=None)
    is_archived = fields.Boolean(load_default=None)
    sort = fields.String(load_default=None)
    order = fields.String(load_default=None, validate=validate.OneOf(["asc", "desc"]))


class QuestionnaireCloneRequestSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=180))
    version = fields.String(required=True, validate=validate.Length(min=1, max=80))
    description = fields.String(required=False, validate=validate.Length(max=2000))


class EvaluationListQuerySchema(PaginationSchema):
    status = fields.String(load_default=None)
    age_min = fields.Integer(load_default=None)
    age_max = fields.Integer(load_default=None)
    date_from = fields.Date(load_default=None)
    date_to = fields.Date(load_default=None)
    psychologist_id = fields.String(load_default=None)
    subject_id = fields.String(load_default=None)
    sort = fields.String(load_default=None)
    order = fields.String(load_default=None, validate=validate.OneOf(["asc", "desc"]))


class EvaluationStatusSchema(Schema):
    status = fields.String(required=True)


class EmailUnsubscribeListQuerySchema(PaginationSchema):
    email = fields.String(load_default=None)
    from_date = fields.DateTime(load_default=None)
    to_date = fields.DateTime(load_default=None)
    sort = fields.String(load_default=None)
    order = fields.String(load_default=None, validate=validate.OneOf(["asc", "desc"]))


class PsychologistDecisionSchema(Schema):
    reason = fields.String(required=True, validate=validate.Length(min=4, max=500))
