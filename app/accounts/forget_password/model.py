from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.db.base import Base


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    otp_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    verified = Column(Boolean, default=False)
    attempt_count = Column(Integer, default=0)
    request_count = Column(Integer, default=0)
    last_requested_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
