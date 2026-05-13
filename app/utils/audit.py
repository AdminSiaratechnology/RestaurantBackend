# app/utils/audit.py
from fastapi import APIRouter, Depends
from typing import Optional, Dict, Any
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, Request
from datetime import datetime
from app.accounts.auditlog.model import AuditLog
from app.accounts.auth.model import authenticate_user
from app.accounts.deps import require_super_admin
from app.accounts.partner.model import Partner
from app.core.security import create_access_token
from app.db.config import SessionDep


router = APIRouter(prefix="/auditlog", tags=["Audit Log"])

async def log_action(
    db: AsyncSession,
    *,
    table_name: str,
    action: str,
    record_id: Optional[int] = None,
    changed_by: Optional[int] = None,
    old_data: Optional[Dict[str, Any]] = None,
    new_data: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
):
    ip_address = None

    if request:
        ip_address = request.client.host

    log = AuditLog(
        table_name=table_name,
        action=action,
        record_id=str(record_id) if record_id else None,
        changed_by=changed_by,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address,
        timestamp=datetime.utcnow(),
    )

    db.add(log)



@router.delete("/partners/{partner_id}")
async def delete_partner(
    partner_id: int,
    db: SessionDep,
    current=Depends(require_super_admin),
    request: Request = None,
):
    partner = await db.get(Partner, partner_id)

    if not partner:
        raise HTTPException(status_code=404, detail="Invalid partner_id")

    if not partner.is_active:
        raise HTTPException(status_code=400, detail="Already inactive")

    old_data = {"is_active": partner.is_active}

    partner.is_active = False

    new_data = {"is_active": partner.is_active}

    await log_action(
        db,
        table_name="partners",
        action="DEACTIVATE",
        record_id=partner.id,
        changed_by=current["user"].id,
        old_data=old_data,
        new_data=new_data,
        request=request,
    )

    await db.commit()

    return {"message": "Partner deactivated successfully"}


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: SessionDep = Depends(),
    request: Request = None,
):
    user = await authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"user_id": user.id})

    # 🔥 Audit log for login
    await log_action(
        db,
        table_name="auth",
        action="LOGIN",
        record_id=user.id,
        changed_by=user.id,
        new_data={"email": user.email},
        request=request,
    )

    await db.commit()

    return {"access_token": access_token, "token_type": "bearer"}