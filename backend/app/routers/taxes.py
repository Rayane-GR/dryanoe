import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import TaxDeclaration
from app.schemas import G50Request, TaxDeclarationRead
from app.services.accounting import g50_figures, get_company_or_404, money

router = APIRouter(prefix="/tax-declarations", tags=["taxes"])

# G50 is filed monthly, by the 20th of the month following the period.
FILING_DAY = 20


def _g50_due_date(period_end: date) -> date:
    if period_end.month == 12:
        return date(period_end.year + 1, 1, FILING_DAY)
    return date(period_end.year, period_end.month + 1, FILING_DAY)


@router.get("", response_model=list[TaxDeclarationRead])
def list_declarations(
    company_id: uuid.UUID,
    declaration_type: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    stmt = select(TaxDeclaration).where(TaxDeclaration.company_id == company_id)
    if declaration_type:
        stmt = stmt.where(TaxDeclaration.type == declaration_type)
    return db.scalars(
        stmt.order_by(TaxDeclaration.period_end.desc()).limit(limit)
    ).all()


@router.post("/g50", response_model=TaxDeclarationRead, status_code=201)
def compute_g50(payload: G50Request, db: Session = Depends(get_db)):
    """Compute a G50 from accounts 4456/4457 and revenue (70x) for the period."""
    get_company_or_404(db, payload.company_id)
    if payload.period_end < payload.period_start:
        raise HTTPException(status_code=400, detail="period_end is before period_start")

    figures = g50_figures(db, payload.company_id, payload.period_start, payload.period_end)
    tap_rate = (
        payload.tap_rate
        if payload.tap_rate is not None
        else Decimal(str(settings.default_tap_rate))
    )
    declaration = TaxDeclaration(
        company_id=payload.company_id,
        type="G50",
        period_start=payload.period_start,
        period_end=payload.period_end,
        tva_collected=figures["tva_collected"],
        tva_deductible=figures["tva_deductible"],
        tva_due=figures["tva_due"],
        tap_amount=money(figures["revenue_ht"] * tap_rate),
        status="draft",
        due_date=_g50_due_date(payload.period_end),
    )
    db.add(declaration)
    db.commit()
    db.refresh(declaration)
    return declaration


@router.post("/{declaration_id}/file", response_model=TaxDeclarationRead)
def file_declaration(declaration_id: uuid.UUID, db: Session = Depends(get_db)):
    declaration = db.get(TaxDeclaration, declaration_id)
    if declaration is None:
        raise HTTPException(status_code=404, detail="Declaration not found")
    if declaration.status != "draft":
        raise HTTPException(status_code=409, detail=f"Declaration is already {declaration.status}")
    declaration.status = "filed"
    declaration.filed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(declaration)
    return declaration


@router.post("/{declaration_id}/pay", response_model=TaxDeclarationRead)
def pay_declaration(declaration_id: uuid.UUID, db: Session = Depends(get_db)):
    declaration = db.get(TaxDeclaration, declaration_id)
    if declaration is None:
        raise HTTPException(status_code=404, detail="Declaration not found")
    if declaration.status == "draft":
        raise HTTPException(status_code=409, detail="File the declaration before paying it")
    declaration.status = "paid"
    db.commit()
    db.refresh(declaration)
    return declaration
