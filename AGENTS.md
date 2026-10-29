# AGENTS.md — MouHassaBa

Accounting API for the Algerian SCF. This repository contains **only the database
and REST API** (no application UI yet); the README is the product spec.

## Running it

```bash
docker compose -f docker-compose.base44.yml up -d
```

- `db` (postgres:16-alpine) → `migrate` (one-shot) → `seed` (one-shot) → `api`.
- `api` runs `uvicorn --reload` from the bind-mounted `./backend`, listening on
  host port **3000**. Dependencies are pinned in `backend/requirements.txt` and
  installed at container start, so a dependency change needs
  `docker compose -f docker-compose.base44.yml up -d --build` (or a restart).
- `./backend` is mounted whole: edits under `app/` and `scripts/` reload the
  server; models/schema changes also need a migration (below).
- Logs: `docker compose -f docker-compose.base44.yml logs -f api`.
- Reset everything (drops the Postgres volume and re-seeds):
  `docker compose -f docker-compose.base44.yml down -v && ... up -d`.

## Where to look

- `/` is an HTML index of all endpoints (it must stay HTML: the preview bridge
  cannot inject into a JSON document). `/info` is the same index as JSON,
  `/docs` is Swagger, `/health` is the compose healthcheck.

## Migrations — do not edit an applied file

`backend/scripts/migrate.py` applies `backend/migrations/*.sql` in filename order
and stores each file's SHA-256 in `schema_migrations`. Editing an applied file
aborts the boot with a checksum error; add a new numbered file instead.

`001_initial_schema.sql` is generated from the SQLAlchemy models. When you change
`backend/app/models.py`, regenerate rather than hand-editing:

```bash
docker run --rm -v "$PWD/backend:/app" -w /app python:3.12-slim sh -ec '
pip install --no-cache-dir -q sqlalchemy==2.0.36 psycopg[binary]==3.2.3 >/dev/null
python - <<"PY"
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from app.models import Base
for t in Base.metadata.sorted_tables:
    print(str(CreateTable(t).compile(dialect=postgresql.dialect())).strip() + ";")
    for i in t.indexes:
        print(str(CreateIndex(i).compile(dialect=postgresql.dialect())).strip() + ";")
PY'
```

## Seed data

`backend/scripts/seed.py` runs on every `up` and is idempotent (keyed on the demo
company name "SARL Demo Comptabilité"). It creates the company with the full SCF
chart + journals, two partners, two products, one sale and one purchase invoice
(both confirmed with generated entries) and a draft G50.

## Business rules that are easy to break

- `POST /invoices/{id}/confirm` numbers the invoice (`FV-2026-00001`) and generates
  the balanced entry; drafts carry no number, and a quote (`type=quote`) is never
  numbered — it must be converted to an invoice first.
- Numbering counts only *numbered* invoices of the same type and year, so drafts
  do not consume a number and the invoice being numbered is not counted twice.
- Every generated entry must balance (`assert_balanced`) before posting; posted
  entries are immutable.
- Money is `NUMERIC(15,2)` end to end — never introduce floats.
- TVA (19/9/0) and TAP rates are data/config (`DEFAULT_TAP_RATE`), not constants:
  the README requires them to be confirmed with an Algerian accountant.

## Known gaps (do not assume these work)

- **No authentication.** The `users` table exists but there is no login, JWT or
  role enforcement; every endpoint is open. Do not expose this publicly as-is.
- No PDF/Excel export, no offline sync, no 2FA.
- No automated tests yet — verify with `curl` or the Swagger UI at `/docs`.

## Sandbox notes

No `BASE44_PREVIEW_MODE` overrides are needed: uvicorn does no Host/Origin
checking, and there is no browser client, so no CORS or allowlist config exists.
If a web client is added later, see the platform's single-origin guidance before
choosing ports.

## Verifying a change

```bash
CID=$(curl -s localhost:3000/companies | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["id"])')
curl -s "localhost:3000/reports/trial-balance?company_id=$CID"   # must say "balanced": true
curl -s "localhost:3000/reports/general-journal?company_id=$CID"
```

Any invoice confirmation must leave the trial balance balanced and increase total
debits by the invoice's TTC amount.
