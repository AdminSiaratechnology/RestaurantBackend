from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Who performed the action
    actor_type = Column(String, index=True, nullable=False)   # super_admin, partner, client, staff, system
    actor_id = Column(Integer, index=True, nullable=True)
    actor_name = Column(String, nullable=True)
    actor_email = Column(String, nullable=True)

    # What happened
    action = Column(String, index=True, nullable=False)       # login, logout, create, update, delete
    module = Column(String, index=True, nullable=True)        # Menu, Client, Partner, Order
    table_name = Column(String, index=True, nullable=True)
    record_id = Column(Integer, index=True, nullable=True)

    description = Column(String, nullable=True)

    # Before & After values
    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)

    # Request information
    request_method = Column(String, nullable=True)
    endpoint = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Outcome
    status = Column(String, index=True, nullable=False, default="success")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)