import enum

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)

from sqlalchemy.orm import relationship

from app.accounts.order.enum import OrderType
from app.db.base import Base


# =========================================================
# ORDER SOURCE ENUM
# =========================================================

class OrderSource(str, enum.Enum):

    POS = "pos"

    ONLINE = "online"

    QR = "qr"


# =========================================================
# ORDER MODEL
# =========================================================

class Order(Base):

    __tablename__ = "orders"

    id = Column(
        Integer,
        primary_key=True,
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False,
    )

    table_id = Column(
        Integer,
        ForeignKey("tables.id"),
        nullable=True,
    )

    order_type = Column(
        Enum(
            OrderType,
            values_callable=lambda enum: [
                e.value
                for e in enum
            ],
            name="order_type_enum",
            native_enum=True,
        ),
        nullable=False,
    )

    # =====================================================
    # ORDER SOURCE
    # =====================================================

    source = Column(
        Enum(
            OrderSource,
            values_callable=lambda enum: [
                e.value
                for e in enum
            ],
            name="order_source_enum",
            native_enum=True,
        ),
        nullable=False,
        default=OrderSource.POS,
        server_default="pos",
        index=True,
    )

    customer_name = Column(
        String,
        nullable=True,
    )

    customer_phone = Column(
        String,
        nullable=True,
    )

    notes = Column(
        String,
        nullable=True,
    )

    # =====================================================
    # KITCHEN / MAIN ORDER STATUS
    #
    # pending
    # preparing
    # ready
    # served
    # cancelled
    # =====================================================

    status = Column(
        String,
        default="pending",
        server_default="pending",
        nullable=False,
        index=True,
    )

    total_amount = Column(
        Float,
        default=0,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=True,
    )

    restaurant_session_id = Column(
        Integer,
        ForeignKey("restaurant_sessions.id"),
        nullable=True,
        index=True,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    client = relationship(
        "Client",
    )

    branch = relationship(
        "Branch",
        back_populates="orders",
    )

    table = relationship(
        "Table",
    )

    customer = relationship(
        "Customer",
        back_populates="orders",
        foreign_keys=[customer_id],
    )

    restaurant_session = relationship(
        "RestaurantSession",
        back_populates="orders",
        foreign_keys=[restaurant_session_id],
    )

    order_items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    # =====================================================
    # ONLINE ORDER DETAIL
    # =====================================================

    online_order_detail = relationship(
        "OnlineOrderDetail",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan",
    )


# =========================================================
# ORDER ITEM MODEL
# =========================================================

class OrderItem(Base):

    __tablename__ = "order_items"

    id = Column(
        Integer,
        primary_key=True,
    )

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
        nullable=False,
    )

    item_id = Column(
        Integer,
        ForeignKey(
            "items.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=True,
    )

    quantity = Column(
        Integer,
        nullable=False,
    )

    order_status = Column(
        String,
        default="pending",
        server_default="pending",
        nullable=False,
    )

    unit_price = Column(
        Float,
        nullable=False,
    )

    discount_percent = Column(
        Float,
        default=0,
        nullable=False,
    )

    tax_percent = Column(
        Float,
        default=0,
        nullable=False,
    )

    subtotal = Column(
        Float,
        default=0,
        nullable=False,
    )

    tax_amount = Column(
        Float,
        default=0,
        nullable=False,
    )

    total_price = Column(
        Float,
        default=0,
        nullable=False,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    order = relationship(
        "Order",
        back_populates="order_items",
    )

    item = relationship(
        "Item",
        back_populates="order_items",
    )

    customer = relationship(
        "Customer",
    )

    @property
    def price(self):

        if self.quantity:

            return round(
                (self.total_price or 0) / self.quantity,
                2,
            )

        base = self.unit_price or 0.0
        disc = self.discount_percent or 0.0
        tax = self.tax_percent or 0.0

        discounted = (
            base
            - (base * disc / 100)
        )

        return round(
            discounted
            + (discounted * tax / 100),
            2,
        )