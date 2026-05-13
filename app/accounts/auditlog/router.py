from fastapi import Depends
from sqlalchemy import func, select
from app import db
from app.accounts.auditlog.model import AuditLog
from fastapi import APIRouter
from app.accounts.deps import require_super_admin
from app.accounts.partner.model import Partner
from app.accounts.partner.schema import PartnerCreate
from app.api.routes import partner
from app.db.config import SessionDep
from datetime import datetime
from app.models import user

router = APIRouter(prefix="/auditlog", tags=["Audit Log"])


async def log_action(
    db: SessionDep,
    current: dict | None,
    action: str,
    table_name: str,
    record_id: str,
    old_data: dict | None = None,
    new_data: dict | None = None,
    ip: str | None = None
):
    log = AuditLog(
        table_name=table_name,
        record_id=str(record_id),
        action=action,
        old_data=old_data,
        new_data=new_data,
        changed_by=current["user"].id if current else None,
        ip_address=ip
    )

    db.add(log)

    async def log_action(
        db: SessionDep,
        current: dict | None,
        action: str,
        table_name: str,
        record_id: str,
        old_data: dict | None = None,
        new_data: dict | None = None,
        ip: str | None = None
    ):
        log = AuditLog(
            table_name=table_name,
            record_id=str(record_id),
            action=action,
            old_data=old_data,
            new_data=new_data,
            changed_by=current["user"].id if current else None,
            ip_address=ip
        )

        db.add(log)
        await db.commit()   # ✅ important



@router.get("/audit-logs")
async def get_logs(
    db: SessionDep,
    current=Depends(require_super_admin),
    page: int = 1,
    page_size: int = 10,
    table_name: str | None = None,
    action: str | None = None,
    changed_by: int | None = None,
):
    query = select(AuditLog)

    if table_name:
        query = query.where(AuditLog.table_name == table_name)

    if action:
        query = query.where(AuditLog.action == action)

    if changed_by:
        query = query.where(AuditLog.changed_by == changed_by)

    # 🔢 Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # 📄 Pagination
    offset = (page - 1) * page_size

    query = (
        query.order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": result.scalars().all()
    }

    await log_action(
        db,
        current,
        action="CREATE",
        table_name="partners",
        record_id=partner.id,
        new_data={"name": partner.name}
    )

    await db.commit()


    await log_action(
        db,
        {
            "user": user,
            "role": user.role
        },
        action="LOGIN",
        table_name="auth",
        record_id=user.id,
        new_data={"email": user.email}
    )

    await db.commit()

    
@router.post("/partners")
async def create_partner(
    data: PartnerCreate,
    db: SessionDep,
    current=Depends(require_super_admin)
):
    partner = Partner(**data.dict())
    db.add(partner)
    await db.commit()
    await db.refresh(partner)

    # ✅ AUDIT LOG
    await log_action(
        db,
        current,
        action="CREATE",
        table_name="partners",
        record_id=partner.id,
        new_data={"name": partner.name}
    )
    return partner


@router.put("/partners/{partner_id}")
async def update_partner(
    partner_id: int,
    data: PartnerCreate,
    db: SessionDep,
    current=Depends(require_super_admin)
):
    partner = await db.get(Partner, partner_id)

    old_data = {"name": partner.name}

    for key, value in data.dict(exclude_unset=True).items():
        setattr(partner, key, value)

    await db.commit()

    # ✅ AUDIT LOG
    await log_action(
        db,
        current,
        action="UPDATE",
        table_name="partners",
        record_id=partner.id,
        old_data=old_data,
        new_data=data.dict(exclude_unset=True)
    )
    return partner



@router.delete("/partners/{partner_id}")
async def delete_partner(
    partner_id: int,
    db: SessionDep,
    current=Depends(require_super_admin)
):
    partner = await db.get(Partner, partner_id)

    partner.is_active = False
    await db.commit()

    # ✅ AUDIT LOG
    await log_action(
        db,
        current,
        action="DELETE",
        table_name="partners",
        record_id=partner.id,
        old_data={"name": partner.name}
    )
    return {"msg": "Partner deactivated"}


@router.get("/audit-logs/partners")
async def get_partner_logs(
    db: SessionDep,
    current=Depends(require_super_admin),
    page: int = 1,
    page_size: int = 10,
):
    query = select(AuditLog).where(AuditLog.table_name == "partners")

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    offset = (page - 1) * page_size

    result = await db.execute(
        query.order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(page_size)
    )

    return {
        "total": total,
        "page": page,
        "data": result.scalars().all()
    }


from sqlalchemy import select, and_

@router.get("/audit-logs")
async def get_partner_logs(
    db: SessionDep,
    current=Depends(require_super_admin),
    partner_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    skip: int = 0,
    limit: int = 20,
):
    query = select(AuditLog)

    filters = []

    if partner_id:
        filters.append(AuditLog.record_id == str(partner_id))

    if start_date:
        filters.append(AuditLog.timestamp >= start_date)

    if end_date:
        filters.append(AuditLog.timestamp <= end_date)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)

    result = await db.execute(query)

    logs = result.scalars().all()

    return logs