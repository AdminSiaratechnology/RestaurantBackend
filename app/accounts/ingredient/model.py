from datetime import datetime

from sqlalchemy.orm import relationship
from sqlalchemy import (
    Boolean,
    Float,
    Column,
    ForeignKey,
    Integer,
    String,
    DateTime,
    UniqueConstraint
)

from app.db.base import Base

class ItemIngredient(Base):
    __tablename__ = "item_ingredients"

    id = Column(Integer, primary_key=True)

    item_id = Column(
        Integer,
        ForeignKey("items.id"),
        nullable=False
    )

    inventory_item_id = Column(
        Integer,
        ForeignKey("inventory_items.id"),
        nullable=False
    )

    godown_id = Column(
        Integer,
        ForeignKey("godowns.id"),
        nullable=False
    )

    quantity_required = Column(
        Float,
        nullable=False
    )

    item = relationship(
        "Item",
        back_populates="ingredients"
    )

    inventory_item = relationship(
        "InventoryItem",
        back_populates="item_ingredients"
    )

    godown = relationship(
        "Godown"
    )