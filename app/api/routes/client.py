from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.db.config import SessionDep
from app.accounts.client.model import Client
from app.accounts.deps import get_current_user
from app.accounts.deps import require_client, require_super_admin

router = APIRouter(prefix="/client", tags=["Client"])



@router.get("/me")
async def get_my_profile(
    current=Depends(require_client)
):
    return current["user"]