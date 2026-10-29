import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, StockMovement
from app.schemas import StockMovementCreate, StockMovementRead

router = APIRouter(prefix="/stock-movements", tags=["stock"])


@router.get("", response_model=list[StockMovementRead])
def list_movements(
    company_id: uuid.UUID,
    product_id: uuid.UUID | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    stmt = select(StockMovement).where(StockMovement.company_id == company_id)
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    return db.scalars(
        stmt.order_by(StockMovement.created_at.desc()).limit(limit)
    ).all()


@router.post("", response_model=StockMovementRead, status_code=201)
def create_movement(payload: StockMovementCreate, db: Session = Depends(get_db)):
    product = db.get(Product, payload.product_id)
    if product is None or product.company_id != payload.company_id:
        raise HTTPException(status_code=400, detail="Product not found for this company")

    delta = Decimal(payload.quantity)
    if payload.movement_type == "out":
        if product.stock_qty - delta < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock: {product.stock_qty} available",
            )
        product.stock_qty = product.stock_qty - delta
    else:
        product.stock_qty = product.stock_qty + delta

    movement = StockMovement(**payload.model_dump())
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement
