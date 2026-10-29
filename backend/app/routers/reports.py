import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JournalEntry
from app.schemas import EntryRead
from app.services.accounting import trial_balance

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/trial-balance")
def get_trial_balance(
    company_id: uuid.UUID,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
):
    """Balances of every account with posted movements; totals must be equal."""
    return trial_balance(db, company_id, start, end)


@router.get("/general-journal", response_model=list[EntryRead])
def get_general_journal(
    company_id: uuid.UUID,
    start: date | None = None,
    end: date | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(JournalEntry).where(
        JournalEntry.company_id == company_id, JournalEntry.is_posted.is_(True)
    )
    if start:
        stmt = stmt.where(JournalEntry.entry_date >= start)
    if end:
        stmt = stmt.where(JournalEntry.entry_date <= end)
    stmt = stmt.order_by(JournalEntry.entry_date, JournalEntry.entry_number)
    return db.scalars(stmt.offset(offset).limit(limit)).all()


@router.get("/ledger")
def get_ledger(
    company_id: uuid.UUID,
    account_code: str,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
):
    """Movements and running balance of a single account."""
    from app.models import JournalEntryLine

    stmt = (
        select(JournalEntryLine, JournalEntry)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.is_posted.is_(True),
            JournalEntryLine.account_code == account_code,
        )
        .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
    )
    if start:
        stmt = stmt.where(JournalEntry.entry_date >= start)
    if end:
        stmt = stmt.where(JournalEntry.entry_date <= end)

    balance = 0
    movements = []
    for line, entry in db.execute(stmt).all():
        balance += float(line.debit) - float(line.credit)
        movements.append(
            {
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date,
                "label": line.label,
                "debit": line.debit,
                "credit": line.credit,
                "balance": round(balance, 2),
            }
        )
    return {"account_code": account_code, "movements": movements, "final_balance": round(balance, 2)}
