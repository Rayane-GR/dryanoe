import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Journal
from app.schemas import JournalRead

router = APIRouter(prefix="/journals", tags=["journals"])


@router.get("", response_model=list[JournalRead])
def list_journals(company_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(
        select(Journal).where(Journal.company_id == company_id).order_by(Journal.code)
    ).all()
