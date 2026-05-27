from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from jose import jwt, JWTError

from app.core.settings import settings  # ✅ Load from central settings

def create_access_token(data: dict):
    to_encode = data.copy()

    # ✅ Use UTC timezone-aware datetime (BEST PRACTICE)
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # ✅ Standard JWT claims
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # issued at
    })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # ✅ Extra safety validation (defensive programming)
        if "user_id" not in payload or "role" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        return payload

    except JWTError:
        # ❌ Do NOT expose internal error in production
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )