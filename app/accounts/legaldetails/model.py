# app/accounts/legaldetails/model.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    func
)

from sqlalchemy.orm import relationship

from app.db.base import Base


class LegalCompliance(Base):
    __tablename__ = "legal_compliances"

    id = Column(Integer, primary_key=True, index=True)

    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    gst_vat_number = Column(String, nullable=True)

    fssai_license_no = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # relationship
    branch = relationship(
        "Branch",
        back_populates="legal_compliance"
    )