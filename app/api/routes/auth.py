from fastapi import APIRouter, HTTPException
from app.schemas.auth import LoginRequest
from app.services.auth_services import authenticate_user
from app.db.config import SessionDep

router = APIRouter()


@router.post("/auth/login")
async def login(data: LoginRequest, db: SessionDep):
    result = await authenticate_user(db, data.email, data.password)
    print(result)
    if not result:
        raise HTTPException(401, "Invalid credentials")

    token, role = result

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role.value
    }