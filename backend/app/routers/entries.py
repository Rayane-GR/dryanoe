import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JournalEntry, JournalEntryLine
from app.schemas import EntryCreate, EntryRead
from app.services.accounting import (
    assert_balanced,
    get_journal,
    next_entry_number,
)

router = APIRouter(prefix="/entries", tags=["journal entries"])


@router.get("", response_model=list[EntryRead])
def list_entries(
    company_id: uuid.UUID,
    journal_code: str | None = None,
    start: date | None = None,
    end: date | None = None,
    posted_only: bool = False,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(JournalEntry).where(JournalEntry.company_id == company_id)
    if journal_code:
        journal = get_journal(db, company_id, journal_code)
        stmt = stmt.where(JournalEntry.journal_id == journal.id)
    if start:
        stmt = stmt.where(JournalEntry.entry_date >= start)
    if end:
        stmt = stmt.where(JournalEntry.entry_date <= end)
    if posted_only:
        stmt = stmt.where(JournalEntry.is_posted.is_(True))
    stmt = stmt.order_by(JournalEntry.entry_date, JournalEntry.entry_number)
    return db.scalars(stmt.offset(offset).limit(limit)).all()


@router.post("", response_model=EntryRead, status_code=201)
def create_entry(payload: EntryCreate, db: Session = Depends(get_db)):
    journal = get_journal(db, payload.company_id, payload.journal_code)
    lines = [JournalEntryLine(**line.model_dump()) for line in payload.lines]
    if payload.is_posted:
        assert_balanced(lines)

    entry = JournalEntry(
        company_id=payload.company_id,
        journal_id=journal.id,
        entry_number=next_entry_number(db, payload.company_id, journal, payload.entry_date),
        entry_date=payload.entry_date,
        reference=payload.reference,
        description=payload.description,
        is_posted=payload.is_posted,
        fiscal_year=payload.entry_date.year,
        lines=lines,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{entry_id}", response_model=EntryRead)
def get_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.post("/{entry_id}/post", response_model=EntryRead)
def post_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    """Post (finalise) an entry. Posted entries are immutable."""
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.is_posted:
        raise HTTPException(status_code=409, detail="Entry is already posted")
    assert_balanced(entry.lines)
    entry.is_posted = True
    db.commit()
    db.refresh(entry)
    return entry
