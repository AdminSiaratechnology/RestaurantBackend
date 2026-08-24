from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class CustomerNote(Base):
    __tablename__ = "customer_notes"

    # =========================================================
    # PRIMARY KEY
    # =========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # =========================================================
    # CUSTOMER
    # =========================================================

    customer_id = Column(
        Integer,
        ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # TENANT
    # =========================================================

    client_id = Column(
        Integer,
        ForeignKey(
            "clients.id",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # BRANCH
    # =========================================================

    branch_id = Column(
        Integer,
        ForeignKey(
            "branches.id",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # NOTE
    # =========================================================

    note = Column(
        Text,
        nullable=False,
    )

    note_type = Column(
        String(50),
        nullable=False,
        default="general",
        server_default="general",
        index=True,
    )

    # =========================================================
    # REMINDER
    # =========================================================

    reminder_date = Column(
        Date,
        nullable=True,
        index=True,
    )

    # =========================================================
    # PIN
    # =========================================================

    is_pinned = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    # =========================================================
    # AUDIT
    # =========================================================

    created_by = Column(
        Integer,
        nullable=True,
        index=True,
    )

    updated_by = Column(
        Integer,
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # =========================================================
    # INDEXES
    # =========================================================

    __table_args__ = (
        Index(
            "ix_customer_notes_customer_branch",
            "customer_id",
            "branch_id",
        ),
        Index(
            "ix_customer_notes_client_branch_customer",
            "client_id",
            "branch_id",
            "customer_id",
        ),
        Index(
            "ix_customer_notes_branch_type",
            "branch_id",
            "note_type",
        ),
        Index(
            "ix_customer_notes_branch_pinned",
            "branch_id",
            "is_pinned",
        ),
        Index(
            "ix_customer_notes_branch_reminder",
            "branch_id",
            "reminder_date",
        ),
    )

    # =========================================================
    # RELATIONSHIPS
    # =========================================================

    customer = relationship(
        "Customer",
        back_populates="notes",
        foreign_keys=[customer_id],
    )