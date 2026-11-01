from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import data, exports
from app.main import app

client = TestClient(app)

ACCOUNTS = {
    "globaltech": ("ops@globaltech.example", "demo-globaltech"),
    "brightmere": ("finance@brightmere.example", "demo-brightmere"),
    "northstar": ("analytics@northstar.example", "demo-northstar"),
}


def login(tenant_id: str) -> dict:
    email, password = ACCOUNTS[tenant_id]
    r = client.post("/api/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"x-session-token": r.json()["token"]}


def export(headers: dict, days: int) -> dict:
    end = data.TODAY
    start = end - timedelta(days=days - 1)
    r = client.post("/api/exports", json={"start": start.isoformat(), "end": end.isoformat()}, headers=headers)
    assert r.status_code == 202, r.text
    return r.json()


@pytest.fixture(autouse=True)
def clear_jobs():
    exports.JOBS.clear()
    yield
    exports.JOBS.clear()


def test_login_rejects_bad_password():
    r = client.post("/api/login", json={"email": "ops@globaltech.example", "password": "nope"})
    assert r.status_code == 401


@pytest.mark.parametrize("tenant_id", ACCOUNTS)
def test_me_reports_tenant(tenant_id):
    r = client.get("/api/me", headers=login(tenant_id))
    assert r.status_code == 200
    assert r.json()["tenant_id"] == tenant_id


@pytest.mark.parametrize("tenant_id", ACCOUNTS)
def test_export_within_window_completes(tenant_id):
    headers = login(tenant_id)
    window = client.get("/api/me", headers=headers).json()["export_window_days"]
    job = export(headers, window)
    assert job["status"] == "complete"
    dl = client.get(f"/api/exports/{job['id']}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.text.count("\n") == window + 1  # header plus one row per day


@pytest.mark.parametrize("tenant_id", ACCOUNTS)
def test_export_beyond_window_does_not_complete(tenant_id):
    headers = login(tenant_id)
    window = client.get("/api/me", headers=headers).json()["export_window_days"]
    job = export(headers, window + 1)
    assert job["status"] != "complete"
    dl = client.get(f"/api/exports/{job['id']}/download", headers=headers)
    assert dl.status_code == 409


def test_export_is_tenant_scoped():
    job = export(login("northstar"), 7)
    r = client.get(f"/api/exports/{job['id']}", headers=login("globaltech"))
    assert r.status_code == 404


def test_export_rejects_dates_before_retention():
    headers = login("northstar")
    start = data.earliest_available() - timedelta(days=1)
    r = client.post("/api/exports", json={"start": start.isoformat(), "end": data.TODAY.isoformat()}, headers=headers)
    assert r.status_code == 400


@pytest.mark.parametrize("tenant_id", ACCOUNTS)
def test_export_beyond_window_fails_with_reason(tenant_id):
    # ESC-4821: over-window jobs stayed queued forever instead of failing (Product Specification 4.3, 4.4).
    headers = login(tenant_id)
    window = client.get("/api/me", headers=headers).json()["export_window_days"]
    job = export(headers, window + 1)
    status = client.get(f"/api/exports/{job['id']}", headers=headers).json()
    assert status["status"] == "failed"
    assert status["error"] == f"Date range exceeds the export window for your plan ({window} days)."


def test_globaltech_export_window_matches_contract():
    # ESC-4821: GlobalTech is Enterprise with a 365-day window (contract LF-ENT-2026-0117 section 2, Amendment 1).
    headers = login("globaltech")
    assert client.get("/api/me", headers=headers).json()["export_window_days"] == 365
    end = data.TODAY
    r = client.post("/api/exports", json={"start": "2026-01-01", "end": end.isoformat()}, headers=headers)
    assert r.status_code == 202
    assert r.json()["status"] == "complete"
