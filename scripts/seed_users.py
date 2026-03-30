"""
Seed users with predefined roles for testing.

Usage (desde la raiz del repo):
  APP_CONFIG_CLASS=config.settings.DevelopmentConfig python scripts/seed_users.py
"""

import importlib
import os
import sys

# Asegura que el proyecto este en el path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.security import hash_password
from app.models import AppUser, Role, UserRole, db


def get_config_class():
    class_path = os.getenv("APP_CONFIG_CLASS", "config.settings.DevelopmentConfig")
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def main():
    users_to_create = [
        {
            "username": "admin_demo",
            "email": "admin_demo@example.com",
            "full_name": "Admin Demo",
            "role": "ADMIN",
            "user_type": "guardian",
        },
        {
            "username": "psych_demo",
            "email": "psych_demo@example.com",
            "full_name": "Psychologist Demo",
            "role": "PSYCHOLOGIST",
            "user_type": "psychologist",
            "professional_card_number": "COLPSIC-DEMO-001",
        },
        {
            "username": "teacher_demo",
            "email": "teacher_demo@example.com",
            "full_name": "Teacher Demo",
            "role": "TEACHER",
            "user_type": "guardian",
        },
        {
            "username": "guardian_demo",
            "email": "guardian_demo@example.com",
            "full_name": "Guardian Demo",
            "role": "GUARDIAN",
            "user_type": "guardian",
        },
    ]
    default_password = os.getenv("SEED_DEFAULT_PASSWORD", "P4ssw0rd!")

    app = create_app(get_config_class())
    with app.app_context():
        for item in users_to_create:
            role = Role.query.filter_by(name=item["role"]).first()
            if not role:
                print(f"Role {item['role']} no existe, omitiendo usuario {item['username']}")
                continue

            user = AppUser.query.filter(
                (AppUser.username == item["username"]) | (AppUser.email == item["email"])
            ).first()

            if not user:
                user = AppUser(
                    username=item["username"],
                    email=item["email"],
                    full_name=item["full_name"],
                    password=hash_password(default_password),
                    is_active=True,
                    user_type=item.get("user_type", "guardian"),
                    professional_card_number=item.get("professional_card_number"),
                )
                db.session.add(user)
                db.session.flush()  # obtiene id
                print(f"Creado usuario {item['username']}")
            else:
                print(f"Usuario {item['username']} ya existe, actualizando datos basicos")
                user.full_name = item["full_name"]
                user.user_type = item.get("user_type", user.user_type or "guardian")
                if item.get("professional_card_number"):
                    user.professional_card_number = item["professional_card_number"]
                user.is_active = True

            # Asignar rol si no lo tiene
            existing = UserRole.query.filter_by(user_id=user.id, role_id=role.id).first()
            if not existing:
                db.session.add(UserRole(user_id=user.id, role_id=role.id))
                print(f"Asignado rol {item['role']} a {item['username']}")

        db.session.commit()
        print("Seed completado. Password por defecto:", default_password)


if __name__ == "__main__":
    main()
