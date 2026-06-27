from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship

from datetime import datetime
from app.db.base import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(
        Integer,
        primary_key=True
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False
    )

    godown_id = Column(
        Integer,
        ForeignKey("godowns.id"),
        nullable=False
    )

    po_number = Column(
        String,
        unique=True,
        nullable=False
    )

    vendor_name = Column(String)
    vendor_phone = Column(String)

    status = Column(
        String,
        default="pending"
    )
    # pending
    # approved
    # ordered
    # partially_received
    # received
    # cancelled

    total_amount = Column(
        Float,
        default=0
    )

    notes = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    items = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan"
    )



from sqlalchemy.orm import relationship

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True)

    purchase_order_id = Column(
        Integer,
        ForeignKey("purchase_orders.id"),
        nullable=False
    )

    inventory_item_id = Column(
        Integer,
        ForeignKey("inventory_items.id"),
        nullable=False
    )

    quantity = Column(
        Float,
        nullable=False
    )

    unit_price = Column(
        Float,
        default=0
    )

    received_qty = Column(
        Float,
        default=0
    )

    subtotal = Column(
        Float,
        default=0
    )

    purchase_order = relationship(
        "PurchaseOrder",
        back_populates="items"
    )

    inventory_item = relationship(
        "InventoryItem"
    )