from fastapi import APIRouter, Depends
from app.accounts.deps import require_super_admin

router = APIRouter(prefix="/superadmin", tags=["Super Admin"])


@router.get("/dashboard")
async def dashboard(current=Depends(require_super_admin)):
    return {"message": "Welcome Super Admin"}