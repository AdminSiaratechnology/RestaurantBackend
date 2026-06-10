from sqlalchemy import select
from datetime import datetime, timedelta
from app.db.config import SessionDep
from app.accounts.forget_password.model import PasswordResetOTP
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordResetOTPRepository:
    def __init__(self, db: SessionDep):
        self.db = db

    async def get_by_email(self, email: str) -> PasswordResetOTP | None:
        result = await self.db.execute(select(PasswordResetOTP).where(PasswordResetOTP.email == email))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        otp: str,
        expires_in_minutes: int = 10
    ) -> PasswordResetOTP:
        otp_hash = pwd_context.hash(otp)
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

        otp_record = PasswordResetOTP(
            email=email,
            otp_hash=otp_hash,
            expires_at=expires_at,
            verified=False,
            attempt_count=0,
            request_count=1,
            last_requested_at=datetime.utcnow()
        )

        self.db.add(otp_record)
        await self.db.commit()
        await self.db.refresh(otp_record)

        return otp_record

    async def update(
        self,
        otp_record: PasswordResetOTP,
        otp: str | None = None,
        expires_in_minutes: int = 10
    ) -> PasswordResetOTP:
        if otp:
            otp_record.otp_hash = pwd_context.hash(otp)
            otp_record.expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
            otp_record.verified = False
            otp_record.attempt_count = 0

        otp_record.request_count += 1
        otp_record.last_requested_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(otp_record)

        return otp_record

    async def increment_attempts(self, otp_record: PasswordResetOTP) -> PasswordResetOTP:
        otp_record.attempt_count += 1
        await self.db.commit()
        await self.db.refresh(otp_record)
        return otp_record

    async def mark_verified(self, otp_record: PasswordResetOTP) -> PasswordResetOTP:
        otp_record.verified = True
        await self.db.commit()
        await self.db.refresh(otp_record)
        return otp_record

    async def invalidate(self, email: str) -> None:
        result = await self.db.execute(select(PasswordResetOTP).where(PasswordResetOTP.email == email))
        for record in result.scalars().all():
            await self.db.delete(record)
        await self.db.commit()

    def verify_otp(self, plain_otp: str, otp_hash: str) -> bool:
        return pwd_context.verify(plain_otp, otp_hash)
