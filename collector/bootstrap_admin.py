"""Preview administrator deployment configuration.

Secrets stay in Render environment variables and are never committed.
"""
import os


def configured_admin():
    email = os.getenv("WORKFORCE_ADMIN_EMAIL", "").strip().lower()
    name = os.getenv("WORKFORCE_ADMIN_NAME", "Euroteams Admin").strip() or "Euroteams Admin"
    password = os.getenv("WORKFORCE_ADMIN_PASSWORD", "")
    try:
        tenant_id = int(os.getenv("WORKFORCE_ADMIN_TENANT_ID", "1"))
    except ValueError:
        tenant_id = 1
    enabled = bool(email and password and len(password) >= 16 and "@" in email)
    return {
        "email": email,
        "name": name,
        "password": password,
        "tenant_id": tenant_id,
        "enabled": enabled,
    }
