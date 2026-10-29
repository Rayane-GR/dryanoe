"""Load demo data so the API has something to show on first boot (idempotent)."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import (
    Company,
    Invoice,
    InvoiceLine,
    JournalEntry,
    Partner,
    Product,
    TaxDeclaration,
)
from app.services.accounting import (
    build_invoice_entry,
    compute_invoice_totals,
    g50_figures,
    money,
    next_invoice_number,
    seed_company_reference_data,
)

DEMO_COMPANY_NAME = "SARL Demo Comptabilité"


def _invoice(db, company, partner, lines, invoice_type, issue_date, due_date) -> Invoice:
    invoice = Invoice(
        company_id=company.id,
        partner_id=partner.id,
        type=invoice_type,
        issue_date=issue_date,
        due_date=due_date,
        status="draft",
        lines=lines,
    )
    compute_invoice_totals(invoice)
    db.add(invoice)
    db.flush()
    invoice.invoice_number = next_invoice_number(db, company.id, invoice_type, issue_date)
    entry = build_invoice_entry(db, invoice)
    db.add(entry)
    db.flush()
    invoice.journal_entry_id = entry.id
    invoice.status = "confirmed"
    return invoice


def main() -> None:
    with SessionLocal() as db:
        existing = db.scalar(select(Company).where(Company.name == DEMO_COMPANY_NAME))
        if existing is not None:
            print(f"demo company already present ({existing.id}) — nothing to seed")
            return

        today = date.today()
        company = Company(
            name=DEMO_COMPANY_NAME,
            nif="099816000123456",
            nis="000916012345678",
            rc="16/00-1234567B22",
            article_imposition="1625031234567",
            address="12 rue Didouche Mourad, Alger Centre, Alger",
            activity_type="legal",
            fiscal_year_start=date(today.year, 1, 1),
            fiscal_year_end=date(today.year, 12, 31),
            currency="DZD",
        )
        db.add(company)
        db.flush()
        seed_company_reference_data(db, company)

        customer = Partner(
            company_id=company.id,
            type="customer",
            name="SARL Nour Distribution",
            nif="099816000654321",
            rc="16/00-7654321B21",
            address="Zone industrielle Rouiba, Alger",
            phone="+213 21 85 12 34",
            email="contact@nour-distribution.dz",
            account_code="4111",
            payment_terms=30,
        )
        supplier = Partner(
            company_id=company.id,
            type="supplier",
            name="EURL Alger Fournitures",
            nif="099816000111222",
            rc="16/00-1112223B20",
            address="5 boulevard Zirout Youcef, Alger",
            phone="+213 21 63 45 67",
            email="ventes@alger-fournitures.dz",
            account_code="4011",
            payment_terms=15,
        )
        service = Product(
            company_id=company.id,
            sku="SRV-COMPTA",
            name="Honoraires de tenue de comptabilité",
            type="service",
            unit_price_ht=Decimal("45000.00"),
            tva_rate=Decimal("19"),
            sales_account="706",
            purchase_account="611",
        )
        hardware = Product(
            company_id=company.id,
            sku="ART-CLAVIER",
            name="Clavier AZERTY filaire",
            type="good",
            unit_price_ht=Decimal("3500.00"),
            tva_rate=Decimal("19"),
            sales_account="7011",
            purchase_account="601",
            stock_qty=Decimal("120.000"),
            stock_min_alert=Decimal("20.000"),
        )
        db.add_all([customer, supplier, service, hardware])
        db.flush()

        sale = _invoice(
            db,
            company,
            customer,
            [
                InvoiceLine(
                    product_id=service.id,
                    description=service.name,
                    quantity=Decimal("1"),
                    unit_price_ht=Decimal("45000.00"),
                    tva_rate=Decimal("19"),
                ),
                InvoiceLine(
                    product_id=hardware.id,
                    description=hardware.name,
                    quantity=Decimal("10"),
                    unit_price_ht=Decimal("3500.00"),
                    tva_rate=Decimal("19"),
                ),
            ],
            "sale",
            today - timedelta(days=10),
            today + timedelta(days=20),
        )
        purchase = _invoice(
            db,
            company,
            supplier,
            [
                InvoiceLine(
                    product_id=hardware.id,
                    description=hardware.name,
                    quantity=Decimal("50"),
                    unit_price_ht=Decimal("2400.00"),
                    tva_rate=Decimal("19"),
                )
            ],
            "purchase",
            today - timedelta(days=6),
            today + timedelta(days=9),
        )
        db.flush()

        period_start = date(today.year, today.month, 1)
        figures = g50_figures(db, company.id, period_start, today)
        declaration = TaxDeclaration(
            company_id=company.id,
            type="G50",
            period_start=period_start,
            period_end=today,
            tva_collected=figures["tva_collected"],
            tva_deductible=figures["tva_deductible"],
            tva_due=figures["tva_due"],
            tap_amount=money(figures["revenue_ht"] * Decimal(str(settings.default_tap_rate))),
            status="draft",
        )
        db.add(declaration)
        db.commit()

        entries = db.scalars(
            select(JournalEntry).where(JournalEntry.company_id == company.id)
        ).all()
        print(
            f"seeded {company.name} ({company.id}): "
            f"{len(entries)} journal entries, sale {sale.invoice_number}, "
            f"purchase {purchase.invoice_number}"
        )


if __name__ == "__main__":
    main()
