from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime

class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: Decimal = Field(gt=0, decimal_places=2, description="Selling price")
    cost: Decimal = Field(ge=0, decimal_places=2, description="Cost price")
    category_id: UUID
    status: str = Field(default="active", description="active, inactive, discontinued")
    is_active: bool = Field(default=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("price", "cost", mode="before")
    @classmethod
    def validate_decimal(cls, value):
        if isinstance(value, str):
            return Decimal(value)
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        valid_statuses = ["active", "inactive", "discontinued"]
        if value.lower() not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return value.lower()


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    cost: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    category_id: Optional[UUID] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    id: UUID
    name: str
    sku: str
    price: Decimal
    status: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}