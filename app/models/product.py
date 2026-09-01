from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, String, DateTime, Text, ForeignKey, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID, uuid4
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"),nullable=False,index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2),nullable=False,comment="Selling price in decimal format")
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2),nullable=False,comment="Cost price for profit tracking")
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"),nullable=False,index=True,
        comment="BUSINESS user who created this product")
    status: Mapped[str] = mapped_column(String(20),default="active",nullable=False,index=True,comment="active, inactive, discontinued")
    is_active: Mapped[bool] = mapped_column(Boolean,default=True,nullable=False,index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc),nullable=False)

    __table_args__ = (
        CheckConstraint("price > 0", name="check_price_positive"),
        CheckConstraint("cost >= 0", name="check_cost_non_negative"),
    )


    category: Mapped["Category"] = relationship("Category", back_populates="products")
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    inventory: Mapped["Inventory"] = relationship(
        "Inventory",
        back_populates="product",
        cascade="all, delete-orphan",
        uselist=False
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="product"
    )
    purchase_order_items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem",
        back_populates="product"
    )