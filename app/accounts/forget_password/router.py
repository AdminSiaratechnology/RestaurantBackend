from fastapi import APIRouter
from app.db.config import SessionDep
from app.accounts.forget_password.schema import (
    OTPRequest,
    OTPVerifyRequest,
    PasswordResetRequest,
    ResetTokenResponse,
    MessageResponse
)
from app.accounts.forget_password.service import PasswordResetService

router = APIRouter(prefix="/password", tags=["Password Management"])


@router.post("/request-otp", response_model=MessageResponse)
async def request_otp(data: OTPRequest, db: SessionDep):
    service = PasswordResetService(db)
    return await service.request_otp(data.email)


@router.post("/verify-otp", response_model=ResetTokenResponse)
async def verify_otp(data: OTPVerifyRequest, db: SessionDep):
    service = PasswordResetService(db)
    return await service.verify_otp(data.email, data.otp)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: PasswordResetRequest, db: SessionDep):
    service = PasswordResetService(db)
    return await service.reset_password(data.reset_token, data.password)
