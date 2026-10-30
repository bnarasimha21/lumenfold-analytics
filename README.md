# Lumenfold Analytics

A small multi-tenant analytics SaaS used for support and engineering demos. Fictional product, fictional customers, synthetic data. Nothing here is real.

Each tenant signs in, sees a dashboard of daily sessions, events and conversions, and can export a CSV for a date range. How far back a tenant can export depends on their plan.

## Run

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 and sign in with one of the demo accounts.

## Demo accounts

One admin account per tenant. The password is always `demo-` followed by the tenant id.

| Tenant | Plan | Email | Password |
|---|---|---|---|
| GlobalTech | Enterprise | ops@globaltech.example | demo-globaltech |
| Brightmere | Starter | finance@brightmere.example | demo-brightmere |
| Northstar | Growth | analytics@northstar.example | demo-northstar |
| Halverson Logistics | Growth | ops@halverson.example | demo-halverson |
| Pinewood Health Partners | Enterprise | data@pinewood.example | demo-pinewood |
| Verdant Grocers | Starter | office@verdant.example | demo-verdant |
| Meridian Travel Group | Growth | digital@meridian.example | demo-meridian |
| Orbital Media Labs | Starter | team@orbital.example | demo-orbital |
| Castellan Insurance | Enterprise | analytics@castellan.example | demo-castellan |
| Bluefin Marine Supply | Starter | admin@bluefin.example | demo-bluefin |
| Ashgrove Education | Growth | platforms@ashgrove.example | demo-ashgrove |
| Tessellate Studio | Starter | hello@tessellate.example | demo-tessellate |
| Kestrel Energy | Enterprise | it@kestrel.example | demo-kestrel |
| Riverbend Credit Union | Growth | digital@riverbend.example | demo-riverbend |
| Solstice Apparel | Starter | ecom@solstice.example | demo-solstice |
| Marlowe Finch Publishing | Growth | audience@marlowe.example | demo-marlowe |
| Quillon Robotics | Enterprise | data@quillon.example | demo-quillon |

## Test

```
.venv/bin/pytest -q
```

## Layout

| Path | What |
|---|---|
| `app/main.py` | FastAPI app: login, dashboard, metrics and export API |
| `app/entitlements.py` | Loads tenants and their plan limits from `config/tenants.json` |
| `app/exports.py` | Export jobs and the worker step that produces the CSV |
| `app/data.py` | Deterministic synthetic daily metrics (400 days of history) |
| `app/templates/` | Login and dashboard pages |
| `config/tenants.json` | Tenant records: plan, export window, modules, demo users |
| `tests/` | pytest suite |

## API

| Method and path | What |
|---|---|
| `POST /api/login` | `{email, password}` returns `{token, tenant_id}`. Send the token as `x-session-token`. |
| `GET /api/me` | Tenant, plan, modules and export window as the app sees them |
| `GET /api/metrics?start=&end=` | Daily rows, up to 90 days |
| `POST /api/exports` | `{start, end}` creates an export job (202) |
| `GET /api/exports/{id}` | Job status: `queued`, `running`, `complete`, `failed` |
| `GET /api/exports/{id}/download` | CSV once complete |
| `GET /healthz` | Health check |

The clock is pinned to 2026-10-30 so the demo is repeatable.
