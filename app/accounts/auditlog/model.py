from datetime import datetime
from sqlalchemy import JSON, Column, DateTime, Integer, String
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String, nullable=False)
    action = Column(String, nullable=False)
    record_id = Column(String)
    changed_by = Column(Integer)

    old_data = Column(JSON)
    new_data = Column(JSON)

    ip_address = Column(String)

    timestamp = Column(DateTime, default=datetime.utcnow)