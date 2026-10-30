"""Tenant entitlement lookup.

Tenants and their entitlements are loaded from config/tenants.json at startup.
The application enforces export limits from this file; it does not read
contracts or any external document store.
"""
import json
import os
from pathlib import Path

CONFIG_PATH = Path(
    os.environ.get("LUMENFOLD_TENANTS", Path(__file__).resolve().parent.parent / "config" / "tenants.json")
)

DEFAULT_EXPORT_WINDOW_DAYS = 90


def load_tenants() -> dict:
    with CONFIG_PATH.open() as f:
        data = json.load(f)
    return {t["id"]: t for t in data["tenants"]}


TENANTS = load_tenants()


def get_tenant(tenant_id: str) -> dict | None:
    return TENANTS.get(tenant_id)


def authenticate(email: str, password: str) -> dict | None:
    """Return the tenant record for a matching user, else None."""
    for tenant in TENANTS.values():
        for user in tenant.get("users", []):
            if user["email"].lower() == email.lower() and user["password"] == password:
                return {"tenant_id": tenant["id"], "email": user["email"], "role": user["role"]}
    return None


def export_window_days(tenant_id: str) -> int:
    tenant = get_tenant(tenant_id)
    if tenant is None:
        return DEFAULT_EXPORT_WINDOW_DAYS
    return int(tenant.get("export_window_days", DEFAULT_EXPORT_WINDOW_DAYS))


def has_module(tenant_id: str, module: str) -> bool:
    tenant = get_tenant(tenant_id)
    return bool(tenant and module in tenant.get("modules", []))
