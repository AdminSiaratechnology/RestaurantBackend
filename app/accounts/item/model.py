from datetime import datetime
from app.accounts.item.enum import FoodType
from sqlalchemy import (
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Boolean,
    DateTime,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    image = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint(
            "name",
            "branch_id",
            name="uq_item_name_per_branch"
        ),
        Index("ix_items_name", "name"),
        Index("ix_items_category_id", "category_id"),
        Index("ix_items_branch_id", "branch_id"),
        Index(
            "ix_items_branch_category_id",
            "branch_id",
            "category_id"
        ),
    )

    client = relationship("Client", back_populates="items")
    category = relationship("Category", back_populates="items")
    branch = relationship("Branch", back_populates="items")

    pricings = relationship("Pricing", back_populates="item", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="item")

    food_type = Column(
        Enum(FoodType, name="food_type_enum"),
        nullable=False,
        default=FoodType.veg
    )

    ingredients = relationship(
        "ItemIngredient",
        back_populates="item",
        cascade="all, delete-orphan"
    )