from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.accounts.partner.model import Partner
from app.db.config import SessionDep
from app.accounts.deps import UserRole, require_client, require_partner, require_roles, require_super_admin

router = APIRouter(prefix="/partner", tags=["Partner"])




@router.get("/me")
async def get_my_profile(
    current=Depends(require_roles(UserRole.PARTNER))
):
    return current["user"]