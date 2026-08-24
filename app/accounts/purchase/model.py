from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# ============================================================
# BRANCH PURCHASE INVOICE COUNTER
# ============================================================

class BranchPurchaseInvoiceCounter(Base):
    __tablename__ = "branch_purchase_invoice_counters"

    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            name="uq_branch_purchase_invoice_counter",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    last_invoice_number = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    branch = relationship(
        "Branch",
        back_populates="purchase_invoice_counter",
    )


# ============================================================
# PURCHASE ENTRY
# ============================================================

class PurchaseEntry(Base):
    __tablename__ = "purchase_entries"

    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "invoice_number",
            name="uq_purchase_invoice_branch",
        ),
        Index(
            "ix_purchase_entries_branch_id",
            "branch_id",
        ),
        Index(
            "ix_purchase_entries_supplier_id",
            "supplier_id",
        ),
        Index(
            "ix_purchase_entries_invoice_date",
            "invoice_date",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
        index=True,
    )

    supplier_id = Column(
        Integer,
        ForeignKey("vendors.id"),
        nullable=False,
        index=True,
    )

    invoice_number = Column(
        String,
        nullable=False,
        index=True,
    )

    invoice_date = Column(
        Date,
        nullable=False,
    )

    supplier_invoice_number = Column(
        String,
        nullable=False,
    )

    supplier_invoice_date = Column(
        Date,
        nullable=False,
    )

    delivery_date = Column(
        Date,
        nullable=True,
    )

    reference_number = Column(
        String,
        nullable=True,
    )

    payment_terms = Column(
        String,
        nullable=True,
    )

    due_date = Column(
        Date,
        nullable=True,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    subtotal = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    tax_amount = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    discount_amount = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    grand_total = Column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    branch = relationship(
        "Branch",
        back_populates="purchase_entries",
    )

    supplier = relationship(
        "Vendor",
    )

    items = relationship(
        "PurchaseEntryItem",
        back_populates="purchase_entry",
        cascade="all, delete-orphan",
    )


# ============================================================
# PURCHASE ENTRY ITEM
# ============================================================

class PurchaseEntryItem(Base):
    __tablename__ = "purchase_entry_items"

    __table_args__ = (
        Index(
            "ix_purchase_entry_items_purchase_id",
            "purchase_entry_id",
        ),
        Index(
            "ix_purchase_entry_items_inventory_id",
            "inventory_item_id",
        ),
        Index(
            "ix_purchase_entry_items_godown_id",
            "godown_id",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    purchase_entry_id = Column(
        Integer,
        ForeignKey(
            "purchase_entries.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # Original inventory item
    inventory_item_id = Column(
        Integer,
        ForeignKey(
            "inventory_items.id",
        ),
        nullable=True,
    )

    # Storage location
    godown_id = Column(
        Integer,
        ForeignKey(
            "godowns.id",
        ),
        nullable=True,
    )

    # ========================================================
    # INVENTORY SNAPSHOT
    # ========================================================

    item_name = Column(
        String,
        nullable=False,
    )

    row_category = Column(
        String,
        nullable=True,
        default="other",
        server_default="other",
    )

    # Base unit
    unit = Column(
        String,
        nullable=False,
    )

    # Purchase/display unit
    display_unit = Column(
        String,
        nullable=True,
    )

    conversion_factor = Column(
        Float,
        nullable=False,
        default=1,
        server_default="1",
    )

    # ========================================================
    # PURCHASE QUANTITY / PRICE
    # ========================================================

    quantity = Column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    reorder_level = Column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    rate = Column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    # ========================================================
    # VENDOR SNAPSHOT
    # ========================================================

    vendor_name = Column(
        String,
        nullable=True,
    )

    vendor_phone = Column(
        String,
        nullable=True,
    )

    # ========================================================
    # DISCOUNT / TAX
    # ========================================================

    discount_percent = Column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    tax_percent = Column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    amount = Column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    purchase_entry = relationship(
        "PurchaseEntry",
        back_populates="items",
    )

    inventory_item = relationship(
        "InventoryItem",
        back_populates="purchase_items",
    )

    godown = relationship(
        "Godown",
        back_populates="purchase_items",
    )


# ============================================================
# CANONICAL ALIASES
# ============================================================

Purchase = PurchaseEntry
PurchaseItem = PurchaseEntryItem