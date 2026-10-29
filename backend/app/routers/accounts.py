import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ChartOfAccount
from app.schemas import AccountCreate, AccountRead
from app.scf import account_class

router = APIRouter(prefix="/accounts", tags=["chart of accounts"])


@router.get("", response_model=list[AccountRead])
def list_accounts(
    company_id: uuid.UUID,
    account_class_filter: int | None = None,
    q: str | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    stmt = select(ChartOfAccount).where(ChartOfAccount.company_id == company_id)
    if account_class_filter is not None:
        stmt = stmt.where(ChartOfAccount.account_class == account_class_filter)
    if q:
        stmt = stmt.where(ChartOfAccount.label.ilike(f"%{q}%") | ChartOfAccount.code.like(f"{q}%"))
    return db.scalars(stmt.order_by(ChartOfAccount.code).limit(limit)).all()


@router.post("", response_model=AccountRead, status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["account_class"] = data.get("account_class") or account_class(data["code"])
    account = ChartOfAccount(**data)
    db.add(account)
    try:
        db.commit()
    except Exception as exc:  # duplicate (company_id, code)
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Account already exists: {exc.orig}") from exc
    db.refresh(account)
    return account
