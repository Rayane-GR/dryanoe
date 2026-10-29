import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Partner
from app.schemas import PartnerCreate, PartnerRead

router = APIRouter(prefix="/partners", tags=["partners"])


@router.get("", response_model=list[PartnerRead])
def list_partners(
    company_id: uuid.UUID,
    partner_type: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(Partner).where(Partner.company_id == company_id)
    if partner_type:
        stmt = stmt.where(Partner.type.in_([partner_type, "both"]))
    if q:
        stmt = stmt.where(Partner.name.ilike(f"%{q}%"))
    return db.scalars(stmt.order_by(Partner.name).offset(offset).limit(limit)).all()


@router.post("", response_model=PartnerRead, status_code=201)
def create_partner(payload: PartnerCreate, db: Session = Depends(get_db)):
    partner = Partner(**payload.model_dump())
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


@router.get("/{partner_id}", response_model=PartnerRead)
def get_partner(partner_id: uuid.UUID, db: Session = Depends(get_db)):
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    return partner
