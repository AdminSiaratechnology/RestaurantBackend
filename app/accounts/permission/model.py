from sqlalchemy import Column, Integer, Boolean, ForeignKey
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

    # ✅ Permissions from UI
    manage_orders = Column(Boolean, default=False)
    manage_staff = Column(Boolean, default=False)
    manage_inventory = Column(Boolean, default=False)
    manage_customers = Column(Boolean, default=False)
    manage_reports = Column(Boolean, default=False)
    manage_branches = Column(Boolean, default=False)
    access_billing = Column(Boolean, default=False)
    edit_menu_items = Column(Boolean, default=False)
    manage_tables = Column(Boolean, default=False)
    manage_kitchen = Column(Boolean, default=False)
    manage_offers = Column(Boolean, default=False)
    manage_brands = Column(Boolean, default=False)


    staff = relationship(
        "app.accounts.staff.model.Staff",
        back_populates="permissions"
    )