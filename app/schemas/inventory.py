from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class InventoryBase(BaseModel):
    quantity_on_hand: int = Field(ge=0, description="Current available stock")
    quantity_reserved: int = Field(default=0, ge=0, description="Reserved for pending orders")
    reorder_level: int = Field(default=10, ge=0)
    reorder_quantity: int = Field(default=50, gt=0)


class InventoryCreate(BaseModel):
    product_id: UUID
    quantity_on_hand: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=10, ge=0)
    reorder_quantity: int = Field(default=50, gt=0)


class InventoryUpdate(BaseModel):
    quantity_on_hand: Optional[int] = Field(None, ge=0)
    quantity_reserved: Optional[int] = Field(None, ge=0)
    reorder_level: Optional[int] = Field(None, ge=0)
    reorder_quantity: Optional[int] = Field(None, gt=0)


class InventoryResponse(InventoryBase):
    id: UUID
    product_id: UUID
    quantity_available: int
    last_restock_at: Optional[datetime]
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventorySimpleResponse(BaseModel):
    quantity_available: int
    quantity_on_hand: int

    model_config = {"from_attributes": True}