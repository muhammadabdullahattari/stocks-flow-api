from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Integer, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID, uuid4
from app.database import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"),nullable=False,index=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"),nullable=False,index=True)
    quantity: Mapped[int] = mapped_column(Integer,nullable=False,comment="Quantity ordered")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2),nullable=False,comment="Price at time of order")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2),nullable=False,comment="quantity * unit_price")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),
        nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
        CheckConstraint("unit_price > 0", name="check_unit_price_positive"),
        CheckConstraint("subtotal > 0", name="check_subtotal_positive"),)

    order: Mapped["Order"] = relationship("Order", back_populates="order_items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")