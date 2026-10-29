import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company
from app.schemas import CompanyCreate, CompanyRead
from app.services.accounting import get_company_or_404, seed_company_reference_data

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=201)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """Create a company and load its standard SCF chart of accounts and journals."""
    company = Company(**payload.model_dump())
    db.add(company)
    db.flush()
    seed_company_reference_data(db, company)
    db.refresh(company)
    return company


@router.get("", response_model=list[CompanyRead])
def list_companies(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    return db.scalars(
        select(Company).order_by(Company.created_at).offset(offset).limit(limit)
    ).all()


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(company_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_company_or_404(db, company_id)
