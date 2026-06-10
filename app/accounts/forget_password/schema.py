from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class OTPRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address of the user")


class OTPVerifyRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address of the user")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP")


class PasswordResetRequest(BaseModel):
    reset_token: str = Field(..., description="Reset token from OTP verification")
    password: str = Field(..., min_length=8, description="New password")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class ResetTokenResponse(BaseModel):
    reset_token: str


class MessageResponse(BaseModel):
    message: str
