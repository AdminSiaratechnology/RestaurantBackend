from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.db.base import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)


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

    name = Column(String, nullable=False)

    row_category = Column(
        String,
        default="other"
    )

    # Only gm, ml, piece stored in DB
    unit = Column(
        String,
        nullable=False
    )

    display_unit = Column(
        String,
        nullable=False,
        default="piece"
    )

    conversion_factor = Column(
        Float,
        nullable=False,
        default=1
    )

    stock_qty = Column(
        Float,
        default=0,
        nullable=False
    )

    reorder_level = Column(
        Float,
        default=0
    )

    cost_per_unit = Column(
        Float,
        default=0
    )

    vendor_name = Column(String)
    vendor_phone = Column(String)

    status = Column(
        String,
        default="in_stock"
    )

    last_restocked = Column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    item_ingredients = relationship(
        "ItemIngredient",
        back_populates="inventory_item",
        cascade="all, delete-orphan"
    )

class Godown(Base):
    __tablename__ = "godowns"

    id = Column(Integer, primary_key=True)

    branch_id = Column(
        Integer,
        ForeignKey("branches.id")
    )

    name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    address = Column(String, nullable=True)



