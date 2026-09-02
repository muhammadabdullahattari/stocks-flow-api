from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import datetime


class PurchaseOrderItemBase(BaseModel):
    product_id: UUID
    quantity_ordered: int = Field(gt=0)
    unit_cost: Decimal = Field(gt=0, decimal_places=2)
    subtotal: Decimal = Field(gt=0, decimal_places=2)


class PurchaseOrderItemCreate(BaseModel):
    product_id: UUID
    quantity_ordered: int = Field(gt=0)
    unit_cost: Decimal = Field(gt=0, decimal_places=2)


class PurchaseOrderItemResponse(PurchaseOrderItemBase):
    id: UUID
    purchase_order_id: UUID
    quantity_received: int
    received_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseOrderBase(BaseModel):
    supplier_id: UUID
    status: str = Field(default="draft", description="draft, pending, confirmed, received, cancelled")
    expected_delivery_date: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        valid_statuses = ["draft", "pending", "confirmed", "received", "cancelled"]
        if value.lower() not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return value.lower()


class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    items: List[PurchaseOrderItemCreate] = Field(min_items=1)
    expected_delivery_date: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("items")
    @classmethod
    def validate_items(cls, value):
        if not value:
            raise ValueError("Purchase order must have at least 1 item")
        product_ids = [item.product_id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Duplicate products in purchase order")
        return value


class PurchaseOrderUpdate(BaseModel):
    status: Optional[str] = None
    expected_delivery_date: Optional[datetime] = None
    notes: Optional[str] = None


class PurchaseOrderResponse(PurchaseOrderBase):
    id: UUID
    po_number: str
    created_by: UUID
    total_amount: Decimal
    items: List[PurchaseOrderItemResponse]
    actual_delivery_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PurchaseOrderListResponse(BaseModel):
    id: UUID
    po_number: str
    supplier_id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}
    
class ReceiveStockRequest(BaseModel):
    quantity_received: int = Field(gt=0, description="Quantity to receive")


class ReceiveStockResponse(BaseModel):
    po_item_id: UUID
    product_name: str
    quantity_ordered: int
    quantity_received: int
    quantity_pending: int
    received_at: str

    model_config = {"from_attributes": True}
