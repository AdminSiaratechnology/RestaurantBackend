from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Index,
)

from app.db.base import Base


class Vendor(Base):

    __tablename__ = "vendors"

    # =========================================================
    # PRIMARY KEY
    # =========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =========================================================
    # CLIENT OWNERSHIP
    # =========================================================

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    # =========================================================
    # BASIC INFORMATION
    # =========================================================

    vendor_code = Column(
        String(50),
        nullable=False,
        index=True,
    )

    vendor_name = Column(
        String(255),
        nullable=False,
        index=True,
    )

    vendor_type = Column(
        String(50),
        nullable=False,
        default="supplier",
    )

    status = Column(
        String(30),
        nullable=False,
        default="active",
        index=True,
    )

    # =========================================================
    # CONTACT INFORMATION
    # =========================================================

    contact_person = Column(
        String(255),
        nullable=True,
    )

    mobile = Column(
        String(20),
        nullable=False,
    )

    email = Column(
        String(255),
        nullable=True,
    )

    # =========================================================
    # ADDRESS INFORMATION
    # =========================================================

    address = Column(
        String(500),
        nullable=True,
    )

    city = Column(
        String(100),
        nullable=True,
    )

    state = Column(
        String(100),
        nullable=True,
    )

    pincode = Column(
        String(10),
        nullable=True,
    )

    # =========================================================
    # TAX INFORMATION
    # =========================================================

    gstin = Column(
        String(20),
        nullable=True,
    )

    pan_number = Column(
        String(20),
        nullable=True,
    )

    fssai_number = Column(
        String(30),
        nullable=True,
    )

    # =========================================================
    # BANKING INFORMATION
    # =========================================================

    bank_name = Column(
        String(255),
        nullable=True,
    )

    account_number = Column(
        String(50),
        nullable=True,
    )

    ifsc_code = Column(
        String(20),
        nullable=True,
    )

    # =========================================================
    # PAYMENT INFORMATION
    # =========================================================

    payment_method = Column(
        String(30),
        nullable=True,
    )

    credit_days = Column(
        Integer,
        nullable=False,
        default=0,
    )

    credit_limit = Column(
        Numeric(14, 2),
        nullable=False,
        default=0,
    )

    # =========================================================
    # BUSINESS INFORMATION
    # =========================================================

    product_categories = Column(
        String(500),
        nullable=True,
    )

    preferred_vendor = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    lead_time_days = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # =========================================================
    # OPTIONAL BRANCH INFORMATION
    #
    # This is NOT used for authorization.
    # Authorization is CLIENT based.
    # =========================================================

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )

    # =========================================================
    # FINANCIAL TRACKING
    # =========================================================

    current_outstanding = Column(
        Numeric(14, 2),
        nullable=False,
        default=0,
    )

    total_purchase_amount = Column(
        Numeric(14, 2),
        nullable=False,
        default=0,
    )

    last_purchase_date = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =========================================================
    # ADDITIONAL INFORMATION
    # =========================================================

    notes = Column(
        String(1000),
        nullable=True,
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

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

    # =========================================================
    # INDEXES
    # =========================================================

    __table_args__ = (
        Index(
            "ix_vendors_client_vendor_code",
            "client_id",
            "vendor_code",
        ),
        Index(
            "ix_vendors_client_vendor_name",
            "client_id",
            "vendor_name",
        ),
    )