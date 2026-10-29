"""MouHassaBa API entry point."""

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import ChartOfAccount, Company, Invoice, Partner
from app.routers import (
    accounts,
    companies,
    entries,
    invoices,
    journals,
    partners,
    products,
    reports,
    stock,
    taxes,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=settings.description,
)

for module in (
    companies,
    accounts,
    partners,
    products,
    journals,
    entries,
    invoices,
    taxes,
    reports,
    stock,
):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


ENDPOINT_GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "Companies",
        [
            ("POST", "/companies", "Create a company and load its SCF chart + journals"),
            ("GET", "/companies", "List companies"),
            ("GET", "/companies/{id}", "One company"),
        ],
    ),
    (
        "Chart of accounts",
        [
            ("GET", "/accounts?company_id=", "SCF accounts (add &account_class=4 to filter)"),
            ("POST", "/accounts", "Add a sub-account"),
        ],
    ),
    (
        "Partners & products",
        [
            ("GET", "/partners?company_id=", "Customers and suppliers"),
            ("POST", "/partners", "Create a partner"),
            ("GET", "/products?company_id=", "Products and services"),
            ("POST", "/products", "Create a product"),
        ],
    ),
    (
        "Journals & entries",
        [
            ("GET", "/journals?company_id=", "VE, AC, BQ, CQ, OD"),
            ("GET", "/entries?company_id=", "Journal entries with their lines"),
            ("POST", "/entries", "Create a manual entry"),
            ("POST", "/entries/{id}/post", "Post an entry (debits must equal credits)"),
        ],
    ),
    (
        "Invoices",
        [
            ("GET", "/invoices?company_id=", "Draft and confirmed invoices"),
            ("POST", "/invoices", "Create a draft invoice"),
            ("POST", "/invoices/{id}/confirm", "Number it and generate its journal entry"),
        ],
    ),
    (
        "Stock & taxes",
        [
            ("GET", "/stock-movements?company_id=", "Stock movements"),
            ("POST", "/stock-movements", "Record in / out / inventory"),
            ("GET", "/tax-declarations?company_id=", "G50, IBS, IRG, TAP"),
            ("POST", "/tax-declarations/g50", "Compute a G50 from accounts 4456/4457"),
        ],
    ),
    (
        "Reports",
        [
            ("GET", "/reports/trial-balance?company_id=", "Balances per account"),
            ("GET", "/reports/general-journal?company_id=", "Posted entries"),
            ("GET", "/reports/ledger?company_id=&account_code=", "Account statement"),
        ],
    ),
]

LANDING_STYLE = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: #0b1220; color: #e6edf7;
  font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 900px; margin: 0 auto; padding: 56px 24px 72px; }
h1 { margin: 0; font-size: 27px; letter-spacing: -0.015em; }
.lead { margin: 6px 0 26px; color: #8ba0bd; }
.badge { display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 12px;
  font-weight: 600; letter-spacing: .02em; background: #12303f; color: #56d6a2;
  border: 1px solid #1c4b5e; vertical-align: 6px; margin-left: 10px; }
.stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 26px; padding: 0; list-style: none; }
.stats li { background: #131c2e; border: 1px solid #22304a; border-radius: 10px;
  padding: 10px 16px; font-size: 13px; color: #8ba0bd; }
.stats b { display: block; font-size: 20px; color: #e6edf7; font-weight: 650; }
.actions { display: flex; gap: 10px; margin-bottom: 34px; flex-wrap: wrap; }
.actions a { padding: 9px 16px; border-radius: 8px; font-size: 14px; font-weight: 600;
  text-decoration: none; border: 1px solid #2a3a56; color: #cfe0f5; }
.actions a.primary { background: #2563eb; border-color: #2563eb; color: #fff; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th.group { text-align: left; padding: 20px 0 8px; font-size: 11px; letter-spacing: .1em;
  text-transform: uppercase; color: #6f89a8; font-weight: 700; }
td { padding: 7px 8px 7px 0; border-top: 1px solid #1b2740; vertical-align: top; }
td.note { color: #7f95b1; }
a { color: #7db4ff; text-decoration: none; overflow-wrap: anywhere; }
a:hover { text-decoration: underline; }
.m { display: inline-block; min-width: 46px; padding: 2px 6px; border-radius: 5px;
  font: 700 11px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; text-align: center; }
.m-get { background: #14324a; color: #7db4ff; }
.m-post { background: #1c3a2b; color: #57d68f; }
footer { margin-top: 34px; font-size: 12px; color: #5d7391; }
@media (max-width: 620px) {
  main { padding: 36px 18px 56px; }
  table, tbody, tr, td { display: block; width: 100%; }
  tr { border-top: 1px solid #1b2740; padding: 9px 0; }
  td { border-top: 0; padding: 0 0 2px; }
  th.group { padding: 16px 0 2px; }
  .m { margin-right: 6px; }
  a { overflow-wrap: normal; }
}
"""


def _href(path: str, company: Company | None) -> str:
    base = path.split("?")[0]
    if "company_id=" not in path or company is None:
        return base
    url = f"{base}?company_id={company.id}"
    if "account_code=" in path:
        url += "&account_code=4111"
    return url


def _landing_html(counts: dict, company: Company | None) -> str:
    rows = []
    for group, items in ENDPOINT_GROUPS:
        rows.append(f'<tr><th class="group" colspan="3">{group}</th></tr>')
        for method, path, note in items:
            rows.append(
                f'<tr><td><span class="m m-{method.lower()}">{method}</span></td>'
                f'<td><a href="{_href(path, company)}">{path}</a></td>'
                f'<td class="note">{note}</td></tr>'
            )
    stats = "".join(
        f"<li><b>{value}</b>{label}</li>" for label, value in counts.items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{settings.app_name}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%232563eb'/%3E%3Ctext x='16' y='23' font-size='17' font-family='sans-serif' font-weight='bold' fill='white' text-anchor='middle'%3EM%3C/text%3E%3C/svg%3E">
<style>{LANDING_STYLE}</style>
</head>
<body>
<main>
  <h1>{settings.app_name}<span class="badge">v{settings.version}</span></h1>
  <p class="lead">REST API for Algerian SCF accounting. Database + API only — no application UI.</p>
  <ul class="stats">{stats}</ul>
  <div class="actions">
    <a class="primary" href="/docs">Open Swagger docs</a>
    <a href="/openapi.json">OpenAPI schema</a>
    <a href="/health">Health</a>
    <a href="/info">JSON index</a>
  </div>
  <table><tbody>{''.join(rows)}</tbody></table>
  <footer>Demo data is loaded on first boot; links below use the seeded company.
  Amounts are in DZD and every generated entry is balanced before posting.</footer>
</main>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, tags=["meta"], include_in_schema=False)
def landing(db: Session = Depends(get_db)):
    counts = {
        "Companies": db.scalar(select(func.count(Company.id))),
        "SCF accounts": db.scalar(select(func.count(ChartOfAccount.id))),
        "Partners": db.scalar(select(func.count(Partner.id))),
        "Invoices": db.scalar(select(func.count(Invoice.id))),
    }
    company = db.scalar(select(Company).order_by(Company.created_at).limit(1))
    return HTMLResponse(_landing_html(counts, company))


@app.get("/info", tags=["meta"])
def index(db: Session = Depends(get_db)):
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "counts": {
            "companies": db.scalar(select(func.count(Company.id))),
            "accounts": db.scalar(select(func.count(ChartOfAccount.id))),
            "partners": db.scalar(select(func.count(Partner.id))),
            "invoices": db.scalar(select(func.count(Invoice.id))),
        },
        "endpoints": [
            {"method": method, "path": path, "description": note}
            for _, items in ENDPOINT_GROUPS
            for method, path, note in items
        ],
    }
