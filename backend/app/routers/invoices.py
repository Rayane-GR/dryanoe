import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Invoice, InvoiceLine, Partner
from app.schemas import InvoiceCreate, InvoiceRead
from app.services.accounting import (
    build_invoice_entry,
    compute_invoice_totals,
    get_company_or_404,
    next_invoice_number,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    company_id: uuid.UUID,
    invoice_type: str | None = None,
    status: str | None = None,
    partner_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(Invoice).where(Invoice.company_id == company_id)
    if invoice_type:
        stmt = stmt.where(Invoice.type == invoice_type)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if partner_id:
        stmt = stmt.where(Invoice.partner_id == partner_id)
    stmt = stmt.order_by(Invoice.issue_date.desc(), Invoice.created_at.desc())
    return db.scalars(stmt.offset(offset).limit(limit)).all()


@router.post("", response_model=InvoiceRead, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    get_company_or_404(db, payload.company_id)
    partner = db.get(Partner, payload.partner_id)
    if partner is None or partner.company_id != payload.company_id:
        raise HTTPException(status_code=400, detail="Partner not found for this company")

    invoice = Invoice(
        company_id=payload.company_id,
        partner_id=payload.partner_id,
        type=payload.type,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        status="draft",
        converted_from=payload.converted_from,
        lines=[InvoiceLine(**line.model_dump()) for line in payload.lines],
    )
    compute_invoice_totals(invoice)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/{invoice_id}/confirm", response_model=InvoiceRead)
def confirm_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    """Number the invoice and generate its balanced journal entry."""
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail=f"Invoice is already {invoice.status}")
    if invoice.type == "quote":
        raise HTTPException(
            status_code=400,
            detail="A quote (devis) is never numbered: convert it to an invoice first",
        )

    invoice.invoice_number = next_invoice_number(
        db, invoice.company_id, invoice.type, invoice.issue_date
    )
    entry = build_invoice_entry(db, invoice)
    db.add(entry)
    db.flush()
    invoice.journal_entry_id = entry.id
    invoice.status = "confirmed"
    db.commit()
    db.refresh(invoice)
    return invoice
