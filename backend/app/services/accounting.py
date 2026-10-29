"""Accounting rules: sequential numbering, journal entry generation, tax computation."""

import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ChartOfAccount,
    Company,
    Invoice,
    Journal,
    JournalEntry,
    JournalEntryLine,
    Partner,
    Product,
)
from app.scf import DEFAULT_JOURNALS, SCF_ACCOUNTS, account_class

ZERO = Decimal("0.00")
CENT = Decimal("0.01")

INVOICE_PREFIX = {
    "sale": "FV",
    "purchase": "FA",
    "credit_note": "AV",
    "quote": "DV",
}

# Accounts used by the automatic entries.
RECEIVABLE_ACCOUNT = "4111"
PAYABLE_ACCOUNT = "4011"
TVA_COLLECTED_ACCOUNT = "4457"
TVA_DEDUCTIBLE_ACCOUNT = "4456"
SALES_ACCOUNT = "7011"
PURCHASE_ACCOUNT = "601"


def money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def seed_company_reference_data(db: Session, company: Company) -> None:
    """Load the standard SCF chart of accounts and the default journals."""
    for code, label, nature in SCF_ACCOUNTS:
        db.add(
            ChartOfAccount(
                company_id=company.id,
                code=code,
                label=label,
                label_fr=label,
                account_class=account_class(code),
                account_nature=nature,
            )
        )
    for code, label in DEFAULT_JOURNALS:
        db.add(Journal(company_id=company.id, code=code, label=label))
    db.commit()


def get_company_or_404(db: Session, company_id: uuid.UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def get_journal(db: Session, company_id: uuid.UUID, code: str) -> Journal:
    journal = db.scalar(
        select(Journal).where(Journal.company_id == company_id, Journal.code == code)
    )
    if journal is None:
        raise HTTPException(status_code=400, detail=f"Journal {code} is not configured")
    return journal


def next_entry_number(db: Session, company_id: uuid.UUID, journal: Journal, when: date) -> str:
    """Sequential legal numbering per company and journal, e.g. VE-2026-00001."""
    count = db.scalar(
        select(func.count(JournalEntry.id)).where(
            JournalEntry.company_id == company_id,
            JournalEntry.journal_id == journal.id,
            JournalEntry.fiscal_year == when.year,
        )
    )
    return f"{journal.code}-{when.year}-{count + 1:05d}"


def next_invoice_number(db: Session, company_id: uuid.UUID, invoice_type: str, when: date) -> str:
    """Sequential official numbering: only numbered invoices count, so drafts never
    consume a number and the invoice being numbered is not counted twice."""
    prefix = INVOICE_PREFIX[invoice_type]
    count = db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.company_id == company_id,
            Invoice.type == invoice_type,
            Invoice.invoice_number.is_not(None),
            func.extract("year", Invoice.issue_date) == when.year,
        )
    )
    return f"{prefix}-{when.year}-{count + 1:05d}"


def compute_invoice_totals(invoice: Invoice) -> None:
    total_ht = ZERO
    total_tva = ZERO
    for line in invoice.lines:
        line_ht = money(Decimal(line.quantity) * Decimal(line.unit_price_ht))
        line_tva = money(line_ht * Decimal(line.tva_rate) / 100)
        line.line_total_ht = line_ht
        line.line_total_tva = line_tva
        total_ht += line_ht
        total_tva += line_tva
    invoice.total_ht = money(total_ht)
    invoice.total_tva = money(total_tva)
    invoice.total_ttc = money(total_ht + total_tva)


def _partner_account(partner: Partner | None, fallback: str) -> str:
    return (partner.account_code if partner and partner.account_code else fallback)


def build_invoice_entry(db: Session, invoice: Invoice) -> JournalEntry:
    """Create the balanced journal entry for a confirmed invoice."""
    assert invoice.company_id is not None and invoice.id is not None
    partner = db.get(Partner, invoice.partner_id) if invoice.partner_id else None
    is_sale = invoice.type in ("sale", "credit_note")
    journal_code = "VE" if is_sale else "AC"
    journal = get_journal(db, invoice.company_id, journal_code)
    entry_date = invoice.issue_date

    lines: list[JournalEntryLine] = []
    grouped: dict[str, Decimal] = {}
    for line in invoice.lines:
        account = None
        if line.product_id:
            product = db.get(Product, line.product_id)
            if product:
                account = product.sales_account if is_sale else product.purchase_account
        account = account or (SALES_ACCOUNT if is_sale else PURCHASE_ACCOUNT)
        grouped[account] = grouped.get(account, ZERO) + line.line_total_ht

    partner_account = _partner_account(
        partner, RECEIVABLE_ACCOUNT if is_sale else PAYABLE_ACCOUNT
    )
    label = f"Facture {invoice.invoice_number}"

    if is_sale:
        lines.append(
            JournalEntryLine(
                account_code=partner_account,
                label=f"{label} - {partner.name if partner else 'Client'}",
                debit=invoice.total_ttc,
                credit=ZERO,
                partner_id=invoice.partner_id,
            )
        )
        for account, amount in sorted(grouped.items()):
            lines.append(JournalEntryLine(account_code=account, label=label, debit=ZERO, credit=money(amount)))
        if invoice.total_tva > ZERO:
            lines.append(
                JournalEntryLine(
                    account_code=TVA_COLLECTED_ACCOUNT,
                    label=f"TVA collectée {label}",
                    debit=ZERO,
                    credit=invoice.total_tva,
                )
            )
    else:
        for account, amount in sorted(grouped.items()):
            lines.append(JournalEntryLine(account_code=account, label=label, debit=money(amount), credit=ZERO))
        if invoice.total_tva > ZERO:
            lines.append(
                JournalEntryLine(
                    account_code=TVA_DEDUCTIBLE_ACCOUNT,
                    label=f"TVA déductible {label}",
                    debit=invoice.total_tva,
                    credit=ZERO,
                )
            )
        lines.append(
            JournalEntryLine(
                account_code=partner_account,
                label=f"{label} - {partner.name if partner else 'Fournisseur'}",
                debit=ZERO,
                credit=invoice.total_ttc,
                partner_id=invoice.partner_id,
            )
        )

    entry = JournalEntry(
        company_id=invoice.company_id,
        journal_id=journal.id,
        entry_number=next_entry_number(db, invoice.company_id, journal, entry_date),
        entry_date=entry_date,
        reference=invoice.invoice_number,
        description=label,
        is_posted=True,
        fiscal_year=entry_date.year,
        lines=lines,
    )
    return entry


def assert_balanced(lines: list[JournalEntryLine]) -> None:
    debits = money(sum((Decimal(line.debit) for line in lines), ZERO))
    credits = money(sum((Decimal(line.credit) for line in lines), ZERO))
    if debits != credits:
        raise HTTPException(
            status_code=400,
            detail=f"Entry is not balanced: debits {debits} != credits {credits}",
        )
    if debits == ZERO:
        raise HTTPException(status_code=400, detail="Entry has no amount")


def trial_balance(db: Session, company_id: uuid.UUID, start: date | None, end: date | None):
    stmt = (
        select(
            JournalEntryLine.account_code,
            func.sum(JournalEntryLine.debit),
            func.sum(JournalEntryLine.credit),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .where(JournalEntry.company_id == company_id, JournalEntry.is_posted.is_(True))
        .group_by(JournalEntryLine.account_code)
        .order_by(JournalEntryLine.account_code)
    )
    if start:
        stmt = stmt.where(JournalEntry.entry_date >= start)
    if end:
        stmt = stmt.where(JournalEntry.entry_date <= end)

    accounts = {
        a.code: a
        for a in db.scalars(select(ChartOfAccount).where(ChartOfAccount.company_id == company_id))
    }
    rows = []
    total_debit = ZERO
    total_credit = ZERO
    for code, debit, credit in db.execute(stmt).all():
        debit = money(debit or 0)
        credit = money(credit or 0)
        account = accounts.get(code)
        rows.append(
            {
                "account_code": code,
                "label": account.label if account else None,
                "account_class": account.account_class if account else account_class(code),
                "debit": debit,
                "credit": credit,
                "balance": money(debit - credit),
            }
        )
        total_debit += debit
        total_credit += credit
    return {
        "rows": rows,
        "total_debit": money(total_debit),
        "total_credit": money(total_credit),
        "balanced": money(total_debit) == money(total_credit),
    }


def g50_figures(db: Session, company_id: uuid.UUID, start: date, end: date) -> dict:
    """TVA and TAP figures for a G50 period, derived from the posted entries."""
    balance = trial_balance(db, company_id, start, end)
    collected = ZERO
    deductible = ZERO
    revenue = ZERO
    for row in balance["rows"]:
        code = row["account_code"]
        if code.startswith("4457"):
            collected += row["credit"] - row["debit"]
        elif code.startswith("4456"):
            deductible += row["debit"] - row["credit"]
        elif code.startswith("70"):
            revenue += row["credit"] - row["debit"]
    return {
        "tva_collected": money(collected),
        "tva_deductible": money(deductible),
        "tva_due": money(collected - deductible),
        "revenue_ht": money(revenue),
    }
