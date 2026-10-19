from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, DateTime, Text, ForeignKey, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID, uuid4
from app.database import Base

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    po_number: Mapped[str] = mapped_column(String(50),unique=True,index=True,nullable=False,
        comment="Auto-generated PO number (e.g., PO-20240115-001)")
    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"),nullable=False,
        index=True,comment="BUSINESS user who created this PO")
    status: Mapped[str] = mapped_column(String(20),default="draft",nullable=False,index=True,
        comment="draft, pending, confirmed, received, cancelled")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2),default=Decimal("0.00"),nullable=False,
        comment="Total PO amount")
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    actual_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),
        nullable=False,index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),nullable=False)

    __table_args__ = (CheckConstraint("total_amount >= 0", name="check_po_total_non_negative"),)

    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="purchase_orders")
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    purchase_order_items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan"
    )

    @property
    def items(self):
        return self.purchase_order_items