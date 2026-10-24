"""Bootstrap a preview administrator from deployment configuration."""
import os


def configured_admin():
    return {
        "email": os.getenv("WORKFORCE_ADMIN_EMAIL", "").strip().lower(),
        "name": os.getenv("WORKFORCE_ADMIN_NAME", "Euroteams Admin").strip(),
        "tenant_id": int(os.getenv("WORKFORCE_ADMIN_TENANT_ID", "1")),
    }
