from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Integer, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID, uuid4
from app.database import Base

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"),nullable=False,index=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"),nullable=False,index=True)
    quantity_ordered: Mapped[int] = mapped_column(Integer,nullable=False,comment="Quantity ordered from supplier")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2),nullable=False,comment="Cost per unit from supplier")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2),nullable=False,comment="quantity_ordered * unit_cost")
    quantity_received: Mapped[int] = mapped_column(Integer,default=0,nullable=False,comment="Actual quantity received")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True,comment="When stock was received and inventory updated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False)

    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="check_po_quantity_positive"),
        CheckConstraint("unit_cost > 0", name="check_po_unit_cost_positive"),
        CheckConstraint("subtotal > 0", name="check_po_subtotal_positive"),
        CheckConstraint("quantity_received >= 0", name="check_quantity_received_non_negative"),)

    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder",back_populates="purchase_order_items")
    product: Mapped["Product"] = relationship("Product", back_populates="purchase_order_items")