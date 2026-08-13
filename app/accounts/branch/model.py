import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# ============================================================
# STATUS ENUM
# ============================================================

class statusEnum(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


# ============================================================
# BRANCH MODEL
# ============================================================

class Branch(Base):
    __tablename__ = "branches"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # BASIC DETAILS
    # ========================================================

    name = Column(
        String,
        nullable=False,
    )

    address = Column(
        String,
        nullable=False,
    )

    city = Column(
        String,
        nullable=False,
    )

    # ========================================================
    # STATUS
    #
    # IMPORTANT:
    # values_callable makes SQLAlchemy store the enum VALUE
    # ("active"/"inactive") instead of the Python enum NAME
    # ("ACTIVE"/"INACTIVE").
    # ========================================================

    status = Column(
        Enum(
            statusEnum,
            name="branch_status_enum",
            native_enum=True,
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=statusEnum.ACTIVE,
        server_default="active",
    )

    # ========================================================
    # CLIENT
    # ========================================================

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    # ========================================================
    # BRAND
    # ========================================================

    brand_id = Column(
        Integer,
        ForeignKey("brands.id"),
        nullable=True,
        index=True,
    )

    # ========================================================
    # BRANCH CODE
    # ========================================================

    branch_code = Column(
        String(5),
        unique=True,
        nullable=False,
        index=True,
    )

    # ========================================================
    # CREATED AT
    # ========================================================

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    client = relationship(
        "Client",
        back_populates="branches",
    )

    brand = relationship(
        "Brand",
        back_populates="branches",
    )

    tables = relationship(
        "Table",
        back_populates="branch",
    )

    orders = relationship(
        "Order",
        back_populates="branch",
    )

    pricings = relationship(
        "Pricing",
        back_populates="branch",
    )

    categories = relationship(
        "Category",
        back_populates="branch",
    )

    items = relationship(
        "Item",
        back_populates="branch",
    )

    tax_settings = relationship(
        "TaxBillingSetting",
        back_populates="branch",
        uselist=False,
    )

    legal_compliance = relationship(
        "LegalCompliance",
        back_populates="branch",
        uselist=False,
    )

    crm_rank_rules = relationship(
        "CRMBranchRankRule",
        back_populates="branch",
        cascade="all, delete-orphan",
    )