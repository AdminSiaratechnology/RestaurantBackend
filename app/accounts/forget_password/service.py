from datetime import datetime, timedelta
from sqlalchemy import select
from fastapi import HTTPException
import logging

from app.db.config import SessionDep
from app.accounts.superadmin.model import SuperAdmin
from app.accounts.partner.model import Partner
from app.accounts.client.model import Client
from app.accounts.staff.model import Staff
from app.accounts.forget_password.repository import PasswordResetOTPRepository
from app.accounts.forget_password.utils import generate_otp, create_reset_token
from app.accounts.auth.utils import hash_password
from app.core.email.service import EmailService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PasswordResetService:
    def __init__(self, db: SessionDep):
        self.db = db
        self.otp_repository = PasswordResetOTPRepository(db)

    async def _find_user_by_email(self, email: str):
        models = [
            (SuperAdmin, "super_admin"),
            (Partner, "partner"),
            (Client, "client"),
            (Staff, "staff"),
        ]

        for model, role in models:
            result = await self.db.execute(
                select(model).where(model.email == email)
            )
            user = result.scalar_one_or_none()
            if user:
                return user, role

        return None, None

    async def request_otp(self, email: str):
        logger.info(f"OTP requested for email: {email}")

        user, _ = await self._find_user_by_email(email)
        if user:
            otp_record = await self.otp_repository.get_by_email(email)

            if otp_record:
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                if otp_record.last_requested_at > one_hour_ago:
                    if otp_record.request_count >= 5:
                        logger.warning(f"Rate limit exceeded for email: {email}")
                        raise HTTPException(
                            status_code=429,
                            detail="Too many requests. Please try again after an hour."
                        )

                otp = generate_otp()
                await self.otp_repository.update(otp_record, otp)
                await EmailService.send_otp_email(email, otp)
                logger.info(f"OTP updated and sent to email: {email}")
            else:
                otp = generate_otp()
                await self.otp_repository.create(email, otp)
                await EmailService.send_otp_email(email, otp)
                logger.info(f"OTP created and sent to email: {email}")

        return {"message": "If the email exists, an OTP has been sent."}

    async def verify_otp(self, email: str, otp: str):
        logger.info(f"Verifying OTP for email: {email}")

        otp_record = await self.otp_repository.get_by_email(email)
        if not otp_record:
            logger.warning(f"No OTP record found for email: {email}")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired OTP"
            )

        if otp_record.verified:
            logger.warning(f"OTP already verified for email: {email}")
            raise HTTPException(
                status_code=400,
                detail="OTP already verified"
            )

        if otp_record.attempt_count >= 5:
            logger.warning(f"Max attempts reached for email: {email}")
            raise HTTPException(
                status_code=400,
                detail="Too many attempts. Please request a new OTP."
            )

        if datetime.utcnow() > otp_record.expires_at:
            logger.warning(f"OTP expired for email: {email}")
            raise HTTPException(
                status_code=400,
                detail="OTP has expired. Please request a new one."
            )

        if not self.otp_repository.verify_otp(otp, otp_record.otp_hash):
            await self.otp_repository.increment_attempts(otp_record)
            logger.warning(f"Invalid OTP for email: {email}")
            raise HTTPException(
                status_code=400,
                detail="Invalid OTP"
            )

        await self.otp_repository.mark_verified(otp_record)

        user, role = await self._find_user_by_email(email)
        if not user:
            logger.warning(f"User not found for email: {email}")
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        reset_token = create_reset_token(user.id, role)
        logger.info(f"OTP verified and reset token created for email: {email}")

        return {"reset_token": reset_token}

    async def reset_password(self, reset_token: str, password: str):
        from app.accounts.forget_password.utils import verify_reset_token

        payload = verify_reset_token(reset_token)
        if not payload:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset token"
            )

        user_id = payload["user_id"]
        role = payload["role"]

        model_map = {
            "super_admin": SuperAdmin,
            "partner": Partner,
            "client": Client,
            "staff": Staff
        }

        model = model_map.get(role)
        if not model:
            raise HTTPException(
                status_code=400,
                detail="Invalid user role"
            )

        result = await self.db.execute(
            select(model).where(model.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        user.password_hash = hash_password(password)
        await self.db.commit()
        logger.info(f"Password reset successfully for user: {user.email}")

        await self.otp_repository.invalidate(user.email)

        return {"message": "Password reset successful"}
