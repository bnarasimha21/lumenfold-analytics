"""Export jobs.

An export request is accepted immediately and processed by a worker step.
Jobs within the tenant's export window complete and produce a CSV. Jobs
outside the window fail with a message the dashboard shows to the user
(Product Specification 4.3).
"""
import csv
import io
import logging
import uuid
from datetime import date, datetime, timezone

from . import data, entitlements

log = logging.getLogger("lumenfold.exports")

JOBS: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request_export(tenant_id: str, start: date, end: date) -> dict:
    job = {
        "id": uuid.uuid4().hex[:12],
        "tenant_id": tenant_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": (end - start).days + 1,
        "status": "queued",
        "created_at": _now(),
        "updated_at": _now(),
        "rows": None,
        "error": None,
    }
    JOBS[job["id"]] = job
    log.info("export %s queued for tenant=%s range=%s..%s (%d days)", job["id"], tenant_id, start, end, job["days"])
    process(job["id"])
    return job


def process(job_id: str) -> None:
    """Worker step. Runs once per job."""
    job = JOBS[job_id]
    window = entitlements.export_window_days(job["tenant_id"])
    if job["days"] > window:
        # Range is outside the tenant's entitlement. A retry cannot succeed,
        # so fail the job rather than leaving it queued (spec 4.3, 4.4).
        log.debug(
            "export %s failed: range of %d days exceeds entitlement window of %d days for tenant=%s",
            job_id, job["days"], window, job["tenant_id"],
        )
        job["status"] = "failed"
        job["error"] = f"Date range exceeds the export window for your plan ({window} days)"
        job["updated_at"] = _now()
        log.info("export %s failed: %s", job_id, job["error"])
        return
    job["status"] = "running"
    job["updated_at"] = _now()
    rows = data.daily_metrics(job["tenant_id"], date.fromisoformat(job["start"]), date.fromisoformat(job["end"]))
    job["rows"] = rows
    job["status"] = "complete"
    job["updated_at"] = _now()
    log.info("export %s complete: %d rows", job_id, len(rows))


def get_job(job_id: str, tenant_id: str) -> dict | None:
    job = JOBS.get(job_id)
    if job is None or job["tenant_id"] != tenant_id:
        return None
    return job


def public(job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in ("rows", "tenant_id")}


def to_csv(job: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["date", "sessions", "events", "conversions", "conversion_rate"])
    writer.writeheader()
    writer.writerows(job["rows"] or [])
    return buf.getvalue()
