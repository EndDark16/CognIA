# api/schemas/password_schema.py

from marshmallow import Schema, fields, validate


class PasswordChangeSchema(Schema):
    current_password = fields.String(required=True, data_key="currentPassword", validate=validate.Length(max=200))
    new_password = fields.String(required=True, data_key="newPassword", validate=validate.Length(max=200))
    confirm_new_password = fields.String(required=True, data_key="confirmNewPassword", validate=validate.Length(max=200))


class PasswordForgotSchema(Schema):
    email = fields.String(required=True, validate=validate.Length(max=254))


class PasswordResetSchema(Schema):
    token = fields.String(required=True, validate=validate.Length(min=10, max=512))
    new_password = fields.String(required=True, data_key="newPassword", validate=validate.Length(max=200))
    confirm_new_password = fields.String(required=True, data_key="confirmNewPassword", validate=validate.Length(max=200))
