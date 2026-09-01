from datetime import datetime, timezone
from sqlalchemy import Integer, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID, uuid4
from app.database import Base


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4) 
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"),unique=True,nullable=False,index=True)
    quantity_on_hand: Mapped[int] = mapped_column(Integer,default=0,nullable=False,comment="Current available stock")
    quantity_reserved: Mapped[int] = mapped_column(Integer,default=0,nullable=False,comment="Reserved for pending orders")
    quantity_available: Mapped[int] = mapped_column(Integer,default=0,nullable=False,comment="on_hand - reserved")
    reorder_level: Mapped[int] = mapped_column(Integer,default=10,nullable=False,comment="Minimum stock level before reordering")
    reorder_quantity: Mapped[int] = mapped_column(Integer,default=50,nullable=False,comment="Quantity to order when below reorder_level")
    last_restock_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc),onupdate=lambda: datetime.now(timezone.utc),nullable=False)

    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="check_on_hand_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="check_reserved_non_negative"),
        CheckConstraint("quantity_available >= 0", name="check_available_non_negative"),
        CheckConstraint("reorder_level >= 0", name="check_reorder_level_non_negative"),
        CheckConstraint("reorder_quantity > 0", name="check_reorder_quantity_positive"),
    )

    product: Mapped["Product"] = relationship("Product", back_populates="inventory")