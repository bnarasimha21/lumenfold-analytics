"""Lumenfold Analytics: a small multi-tenant analytics app used for demos.

Run:  uvicorn app.main:app --reload --port 8000
"""
import logging
import secrets
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import data, entitlements, exports

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lumenfold")

PRODUCT = "Lumenfold Analytics"
app = FastAPI(title=PRODUCT)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

SESSIONS: dict[str, dict] = {}


def current_user(request: Request) -> dict:
    token = request.cookies.get("lf_session") or request.headers.get("x-session-token")
    user = SESSIONS.get(token or "")
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse("/dashboard" if request.cookies.get("lf_session") in SESSIONS else "/login")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str | None = None):
    return templates.TemplateResponse(request, "login.html", {"product": PRODUCT, "error": error})


@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    user = entitlements.authenticate(email, password)
    if not user:
        return RedirectResponse("/login?error=Invalid+email+or+password", status_code=303)
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = user
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("lf_session", token, httponly=True)
    return resp


@app.post("/api/login")
def api_login(payload: dict):
    user = entitlements.authenticate(payload.get("email", ""), payload.get("password", ""))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = user
    return {"token": token, "tenant_id": user["tenant_id"]}


@app.get("/logout")
def logout(request: Request):
    SESSIONS.pop(request.cookies.get("lf_session", ""), None)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("lf_session")
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    try:
        user = current_user(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)
    tenant = entitlements.get_tenant(user["tenant_id"])
    end = data.TODAY
    start = end - timedelta(days=29)
    rows = data.daily_metrics(tenant["id"], start, end)
    totals = {
        "sessions": sum(r["sessions"] for r in rows),
        "events": sum(r["events"] for r in rows),
        "conversions": sum(r["conversions"] for r in rows),
    }
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "product": PRODUCT,
            "tenant": tenant,
            "user": user,
            "rows": rows[-14:][::-1],
            "totals": totals,
            "today": end.isoformat(),
            "default_start": start.isoformat(),
            "earliest": data.earliest_available().isoformat(),
        },
    )


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    tenant = entitlements.get_tenant(user["tenant_id"])
    return {
        "tenant_id": tenant["id"],
        "tenant_name": tenant["name"],
        "plan": tenant["plan"],
        "modules": tenant["modules"],
        "export_window_days": entitlements.export_window_days(tenant["id"]),
        "email": user["email"],
    }


@app.get("/api/metrics")
def metrics(start: date, end: date, user: dict = Depends(current_user)):
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    if (end - start).days + 1 > 90:
        raise HTTPException(status_code=400, detail="Dashboard queries are limited to 90 days. Use an export for longer ranges.")
    return {"rows": data.daily_metrics(user["tenant_id"], start, end)}


@app.post("/api/exports", status_code=202)
def create_export(payload: dict, user: dict = Depends(current_user)):
    if not entitlements.has_module(user["tenant_id"], "exports"):
        raise HTTPException(status_code=403, detail="Exports are not enabled for this account")
    try:
        start = date.fromisoformat(payload["start"])
        end = date.fromisoformat(payload["end"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="start and end must be ISO dates")
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    if start < data.earliest_available():
        raise HTTPException(status_code=400, detail=f"Data is retained from {data.earliest_available().isoformat()}")
    job = exports.request_export(user["tenant_id"], start, end)
    return exports.public(job)


@app.get("/api/exports/{job_id}")
def export_status(job_id: str, user: dict = Depends(current_user)):
    job = exports.get_job(job_id, user["tenant_id"])
    if not job:
        raise HTTPException(status_code=404, detail="Export not found")
    return exports.public(job)


@app.get("/api/exports/{job_id}/download")
def export_download(job_id: str, user: dict = Depends(current_user)):
    job = exports.get_job(job_id, user["tenant_id"])
    if not job:
        raise HTTPException(status_code=404, detail="Export not found")
    if job["status"] != "complete":
        return JSONResponse({"detail": f"Export is {job['status']}"}, status_code=409)
    return PlainTextResponse(
        exports.to_csv(job),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="lumenfold-{job["start"]}-to-{job["end"]}.csv"'},
    )


@app.get("/healthz")
def healthz():
    return {"ok": True, "product": PRODUCT}
