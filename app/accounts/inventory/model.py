from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# =========================================================
# INVENTORY ITEM
# =========================================================

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    __table_args__ = (
        Index("ix_inventory_id", "id"),
        Index("ix_inventory_branch_id", "branch_id"),
        Index("ix_inventory_godown_id", "godown_id"),
        Index("ix_inventory_name", "name"),
        Index("ix_inventory_status", "status"),
        Index(
            "ix_inventory_branch_godown",
            "branch_id",
            "godown_id",
        ),
        Index(
            "ix_inventory_branch_status",
            "branch_id",
            "status",
        ),
    )

    # =====================================================
    # COLUMNS
    # =====================================================

    id = Column(
        Integer,
        primary_key=True,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
    )

    godown_id = Column(
        Integer,
        ForeignKey("godowns.id"),
        nullable=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    row_category = Column(
        String,
        nullable=False,
        default="other",
    )

    unit = Column(
        String,
        nullable=False,
    )

    display_unit = Column(
        String,
        nullable=False,
        default="piece",
    )

    conversion_factor = Column(
        Float,
        nullable=False,
        default=1,
    )

    stock_qty = Column(
        Float,
        nullable=False,
        default=0,
    )

    reorder_level = Column(
        Float,
        nullable=False,
        default=0,
    )

    cost_per_unit = Column(
        Float,
        nullable=False,
        default=0,
    )

    vendor_name = Column(
        String,
        nullable=True,
    )

    vendor_phone = Column(
        String,
        nullable=True,
    )

    status = Column(
        String,
        nullable=False,
        default="in_stock",
    )

    last_restocked = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    item_ingredients = relationship(
        "ItemIngredient",
        back_populates="inventory_item",
        cascade="all, delete-orphan",
    )

    # InventoryItem -> Godown
    godown = relationship(
        "Godown",
        back_populates="inventory_items",
        foreign_keys=[godown_id],
    )

    # InventoryItem -> PurchaseEntryItem
    purchase_items = relationship(
        "PurchaseEntryItem",
        back_populates="inventory_item",
        foreign_keys="PurchaseEntryItem.inventory_item_id",
    )


# =========================================================
# GODOWN
# =========================================================

class Godown(Base):
    __tablename__ = "godowns"

    # =====================================================
    # COLUMNS
    # =====================================================

    id = Column(
        Integer,
        primary_key=True,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
    )

    name = Column(
        String,
        nullable=False,
    )

    code = Column(
        String,
        nullable=True,
    )

    address = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    # Godown -> InventoryItem
    inventory_items = relationship(
        "InventoryItem",
        back_populates="godown",
        foreign_keys="InventoryItem.godown_id",
    )

    # Godown -> PurchaseEntryItem
    #
    # THIS FIXES:
    # Mapper 'Mapper[Godown(godowns)]' has no property
    # 'purchase_items'
    #
    purchase_items = relationship(
        "PurchaseEntryItem",
        back_populates="godown",
        foreign_keys="PurchaseEntryItem.godown_id",
    )