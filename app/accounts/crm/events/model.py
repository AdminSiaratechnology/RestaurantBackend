"""
app/accounts/crm/events/model.py

SQLAlchemy Model for tracking processed CRM events for Database Idempotency.
Guarantees that no event (e.g. bill_completed for bill_id=125) is processed twice even across worker restarts.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, Text
from app.db.base import Base


class CRMProcessedEvent(Base):
    __tablename__ = "crm_processed_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # e.g., "bill_completed"
    reference_id = Column(String(100), nullable=False, index=True) # e.g., bill_id "125"
    client_id = Column(Integer, nullable=False, index=True)
    branch_id = Column(Integer, nullable=False, index=True)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    worker_id = Column(String(100), nullable=True)
    status = Column(String(50), default="SUCCESS", nullable=False)
    details = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("event_type", "reference_id", name="uq_crm_event_reference"),
    )
