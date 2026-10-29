"""Pydantic request/response schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InvoiceType = Literal["sale", "purchase", "credit_note", "quote"]
PartnerType = Literal["customer", "supplier", "both"]
MovementType = Literal["in", "out", "inventory"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Companies -------------------------------------------------------------
class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    nif: str | None = None
    nis: str | None = None
    rc: str | None = None
    article_imposition: str | None = None
    address: str | None = None
    activity_type: Literal["physical", "legal"] | None = None
    fiscal_year_start: date | None = None
    fiscal_year_end: date | None = None
    currency: str = "DZD"


class CompanyRead(ORMModel):
    id: uuid.UUID
    name: str
    nif: str | None
    nis: str | None
    rc: str | None
    article_imposition: str | None
    address: str | None
    activity_type: str | None
    fiscal_year_start: date | None
    fiscal_year_end: date | None
    currency: str
    created_at: datetime


# --- Chart of accounts -----------------------------------------------------
class AccountCreate(BaseModel):
    company_id: uuid.UUID
    code: str = Field(min_length=1, max_length=10)
    label: str = Field(min_length=1, max_length=255)
    label_fr: str | None = None
    account_class: int | None = Field(default=None, ge=1, le=7)
    parent_code: str | None = None
    account_nature: Literal["debit", "credit"] | None = None


class AccountRead(ORMModel):
    id: uuid.UUID
    code: str
    label: str
    label_fr: str | None
    account_class: int
    parent_code: str | None
    account_nature: str | None
    is_active: bool


# --- Journals --------------------------------------------------------------
class JournalRead(ORMModel):
    id: uuid.UUID
    code: str
    label: str | None


# --- Journal entries -------------------------------------------------------
class EntryLineCreate(BaseModel):
    account_code: str = Field(min_length=1, max_length=10)
    label: str | None = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    partner_id: uuid.UUID | None = None


class EntryCreate(BaseModel):
    company_id: uuid.UUID
    journal_code: str = Field(min_length=1, max_length=10)
    entry_date: date
    reference: str | None = None
    description: str | None = None
    is_posted: bool = False
    lines: list[EntryLineCreate] = Field(min_length=1)


class EntryLineRead(ORMModel):
    id: uuid.UUID
    account_code: str
    label: str | None
    debit: Decimal
    credit: Decimal
    partner_id: uuid.UUID | None


class EntryRead(ORMModel):
    id: uuid.UUID
    entry_number: str
    entry_date: date
    reference: str | None
    description: str | None
    is_posted: bool
    fiscal_year: int | None
    journal: JournalRead
    lines: list[EntryLineRead]


# --- Partners --------------------------------------------------------------
class PartnerCreate(BaseModel):
    company_id: uuid.UUID
    type: PartnerType
    name: str = Field(min_length=1, max_length=255)
    nif: str | None = None
    nis: str | None = None
    rc: str | None = None
    article_imposition: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    account_code: str | None = None
    payment_terms: int = 30


class PartnerRead(ORMModel):
    id: uuid.UUID
    type: str
    name: str
    nif: str | None
    nis: str | None
    rc: str | None
    address: str | None
    phone: str | None
    email: str | None
    account_code: str | None
    payment_terms: int


# --- Products --------------------------------------------------------------
class ProductCreate(BaseModel):
    company_id: uuid.UUID
    sku: str | None = None
    name: str = Field(min_length=1, max_length=255)
    type: Literal["good", "service"] | None = None
    unit_price_ht: Decimal | None = None
    tva_rate: Decimal = Decimal("19")
    sales_account: str | None = None
    purchase_account: str | None = None
    stock_qty: Decimal = Decimal("0")
    stock_min_alert: Decimal = Decimal("0")


class ProductRead(ORMModel):
    id: uuid.UUID
    sku: str | None
    name: str
    type: str | None
    unit_price_ht: Decimal | None
    tva_rate: Decimal
    sales_account: str | None
    purchase_account: str | None
    stock_qty: Decimal
    stock_min_alert: Decimal
    is_active: bool


# --- Invoices --------------------------------------------------------------
class InvoiceLineCreate(BaseModel):
    product_id: uuid.UUID | None = None
    description: str | None = None
    quantity: Decimal = Decimal("1")
    unit_price_ht: Decimal = Decimal("0")
    tva_rate: Decimal = Decimal("19")


class InvoiceCreate(BaseModel):
    company_id: uuid.UUID
    partner_id: uuid.UUID
    type: InvoiceType
    issue_date: date
    due_date: date | None = None
    lines: list[InvoiceLineCreate] = Field(min_length=1)
    converted_from: uuid.UUID | None = None


class InvoiceLineRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID | None
    description: str | None
    quantity: Decimal
    unit_price_ht: Decimal
    tva_rate: Decimal
    line_total_ht: Decimal
    line_total_tva: Decimal


class InvoiceRead(ORMModel):
    id: uuid.UUID
    partner_id: uuid.UUID | None
    type: str
    invoice_number: str | None
    issue_date: date
    due_date: date | None
    status: str
    total_ht: Decimal
    total_tva: Decimal
    total_ttc: Decimal
    journal_entry_id: uuid.UUID | None
    lines: list[InvoiceLineRead]


# --- Stock -----------------------------------------------------------------
class StockMovementCreate(BaseModel):
    company_id: uuid.UUID
    product_id: uuid.UUID
    movement_type: MovementType
    quantity: Decimal
    reference_doc: uuid.UUID | None = None
    movement_date: date | None = None


class StockMovementRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    movement_type: str
    quantity: Decimal
    reference_doc: uuid.UUID | None
    movement_date: date | None
    created_at: datetime


# --- Taxes -----------------------------------------------------------------
class G50Request(BaseModel):
    company_id: uuid.UUID
    period_start: date
    period_end: date
    tap_rate: Decimal | None = None


class TaxDeclarationRead(ORMModel):
    id: uuid.UUID
    type: str
    period_start: date | None
    period_end: date | None
    tva_collected: Decimal
    tva_deductible: Decimal
    tva_due: Decimal
    tap_amount: Decimal
    status: str
    due_date: date | None
    filed_at: datetime | None
