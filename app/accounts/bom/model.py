from datetime import datetime
from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from app.db.base import Base


class MenuItemBOM(Base):
    __tablename__ = "menu_item_bom"

    id = Column(Integer, primary_key=True)

    menu_item_id = Column(
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

    qty_required = Column(
        Float,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )