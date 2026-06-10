from datetime import datetime, timedelta
from jose import jwt, JWTError
import secrets

from app.core.settings import settings


def generate_otp() -> str:
    """
    Generate a secure 6-digit OTP using cryptographically secure random numbers
    """
    return str(secrets.randbelow(900000) + 100000)


def create_reset_token(user_id: int, role: str):
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "password_reset",
        "exp": datetime.utcnow() + timedelta(minutes=15)
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def verify_reset_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        if payload.get("type") != "password_reset":
            return None

        return payload

    except JWTError:
        return None
