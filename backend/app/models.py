"""SQLAlchemy models for the SCF accounting schema documented in README.md."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nif: Mapped[str | None] = mapped_column(String(20))
    nis: Mapped[str | None] = mapped_column(String(20))
    rc: Mapped[str | None] = mapped_column(String(30))
    article_imposition: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(Text)
    # 'physical' (individual, IRG) or 'legal' (corporate, IBS)
    activity_type: Mapped[str | None] = mapped_column(String(20))
    fiscal_year_start: Mapped[date | None] = mapped_column(Date)
    fiscal_year_end: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), server_default=text("'DZD'"), nullable=False)

    accounts: Mapped[list["ChartOfAccount"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )
    journals: Mapped[list["Journal"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # admin | accountant | employee
    two_factor_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str | None] = mapped_column(String(50))  # create | update | delete | post
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    diff: Mapped[dict | None] = mapped_column(JSONB)


class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    label_fr: Mapped[str | None] = mapped_column(String(255))
    account_class: Mapped[int] = mapped_column("class", SmallInteger, nullable=False)  # 1..7
    parent_code: Mapped[str | None] = mapped_column(String(10))
    account_nature: Mapped[str | None] = mapped_column(String(10))  # debit | credit
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)

    company: Mapped["Company | None"] = relationship(back_populates="accounts")


class Journal(Base):
    __tablename__ = "journals"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_journals_company_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(10), nullable=False)  # VE, AC, BQ, OD
    label: Mapped[str | None] = mapped_column(String(100))

    company: Mapped["Company | None"] = relationship(back_populates="journals")


class JournalEntry(TimestampMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("company_id", "entry_number", name="uq_entries_company_number"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    journal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journals.id"), nullable=False)
    entry_number: Mapped[str] = mapped_column(String(30), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    is_posted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column(SmallInteger)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    journal: Mapped["Journal"] = relationship(lazy="joined")
    lines: Mapped[list["JournalEntryLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    __table_args__ = (CheckConstraint("debit >= 0 AND credit >= 0", name="ck_entry_line_amounts"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False
    )
    account_code: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    debit: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default=text("0"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")


class Partner(TimestampMixin, Base):
    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # customer | supplier | both
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nif: Mapped[str | None] = mapped_column(String(20))
    nis: Mapped[str | None] = mapped_column(String(20))
    rc: Mapped[str | None] = mapped_column(String(30))
    article_imposition: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    account_code: Mapped[str | None] = mapped_column(String(10))  # 411xxx / 401xxx
    payment_terms: Mapped[int] = mapped_column(SmallInteger, server_default=text("30"), nullable=False)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    sku: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str | None] = mapped_column(String(10))  # good | service
    unit_price_ht: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    tva_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=text("19"), nullable=False)
    sales_account: Mapped[str | None] = mapped_column(String(10))
    purchase_account: Mapped[str | None] = mapped_column(String(10))
    stock_qty: Mapped[Decimal] = mapped_column(Numeric(15, 3), server_default=text("0"), nullable=False)
    stock_min_alert: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), server_default=text("0"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)


class StockMovement(TimestampMixin, Base):
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(10), nullable=False)  # in | out | inventory
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    reference_doc: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    movement_date: Mapped[date | None] = mapped_column(Date)


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "type", "invoice_number", name="uq_invoices_company_type_number"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    partner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("partners.id"))
    type: Mapped[str] = mapped_column(String(15), nullable=False)  # sale | purchase | credit_note | quote
    # Empty until officially numbered: a quote (devis) never gets an invoice number.
    invoice_number: Mapped[str | None] = mapped_column(String(30))
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(15), server_default=text("'draft'"), nullable=False)
    total_ht: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default=text("0"), nullable=False)
    total_tva: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )
    total_ttc: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal_entries.id"))
    converted_from: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"))

    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), server_default=text("1"), nullable=False)
    unit_price_ht: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )
    tva_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=text("19"), nullable=False)
    line_total_ht: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )
    line_total_tva: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")


class TaxDeclaration(Base):
    __tablename__ = "tax_declarations"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # G50 | IBS | IRG | TAP
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    tva_collected: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )
    tva_deductible: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )
    tva_due: Mapped[Decimal] = mapped_column(Numeric(15, 2), server_default=text("0"), nullable=False)
    tap_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), server_default=text("0"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(15), server_default=text("'draft'"), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
