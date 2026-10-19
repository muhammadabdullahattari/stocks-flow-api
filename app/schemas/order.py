from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import datetime


class OrderItemBase(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, description="Quantity must be at least 1")
    unit_price: Decimal = Field(gt=0, decimal_places=2)
    subtotal: Decimal = Field(gt=0, decimal_places=2)


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0)


class OrderItemResponse(OrderItemBase):
    id: UUID
    order_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderBase(BaseModel):
    status: str = Field(default="pending", description="pending, confirmed, shipped, delivered, cancelled")
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
        if value.lower() not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return value.lower()


class OrderCreate(BaseModel):
    items: List[OrderItemCreate] = Field(min_items=1, description="At least 1 item required")
    notes: Optional[str] = None

    @field_validator("items")
    @classmethod
    def validate_items(cls, value):
        if not value:
            raise ValueError("Order must have at least 1 item")
        product_ids = [item.product_id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Duplicate products in order")
        return value


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class OrderResponse(OrderBase):
    id: UUID
    order_number: str
    customer_id: UUID
    total_amount: Decimal
    items: List[OrderItemResponse] = Field(default=[], validation_alias="order_items")
    created_at: datetime
    updated_at: datetime
    delivered_at: Optional[datetime]
    cancelled_at: Optional[datetime]

    model_config = {"from_attributes": True, "populate_by_name": True}


class OrderListResponse(BaseModel):
    id: UUID
    order_number: str
    customer_id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}