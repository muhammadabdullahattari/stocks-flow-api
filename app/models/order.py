from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, DateTime, Text, ForeignKey, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID, uuid4
from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_number: Mapped[str] = mapped_column(String(50),unique=True,index=True,nullable=False,comment="Auto-generated order number (e.g., ORD-20240115-001)")
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"),nullable=False,index=True,comment="CUSTOMER user who placed the order")
    status: Mapped[str] = mapped_column(String(20),default="pending",nullable=False,index=True,comment="pending, confirmed, shipped, delivered, cancelled")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2),default=Decimal("0.00"),nullable=False,comment="Total order amount")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),nullable=False,index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc),nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)

    __table_args__ = (CheckConstraint("total_amount >= 0", name="check_total_amount_non_negative"),)

    customer: Mapped["User"] = relationship("User", foreign_keys=[customer_id])
    order_items: Mapped[list["OrderItem"]] = relationship("OrderItem",back_populates="order",cascade="all, delete-orphan")

    @property
    def items(self):
        return self.order_items