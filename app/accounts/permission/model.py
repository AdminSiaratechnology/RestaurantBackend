from sqlalchemy import Column, Integer, Boolean, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class StaffPermission(Base):
    __tablename__ = "staff_permissions"

    id = Column(Integer, primary_key=True, index=True)

    staff_id = Column(
        Integer,
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    manage_orders = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_staff = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_inventory = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_purchase = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_customers = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_reports = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_branches = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    access_billing = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    edit_menu_items = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_tables = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_kitchen = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_offers = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    manage_brands = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    staff = relationship(
        "app.accounts.staff.model.Staff",
        back_populates="permissions"
    )