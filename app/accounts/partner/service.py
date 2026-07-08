# app/accounts/partner/service.py

from fastapi import HTTPException, Request
from sqlalchemy import select, func
from passlib.context import CryptContext
from datetime import datetime, timedelta

from app.accounts.client.model import Client
from app.accounts.partner.model import Partner
from app.accounts.deps import UserRole
from app.accounts.auditlog.service import create_audit_log
from app.accounts.auditlog.utils import model_to_dict

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# =====================================
# CREATE CLIENT
# =====================================

async def create_client_service(
    db,
    data,
    current,
    request: Request,
):
    if current["role"] == UserRole.SUPER_ADMIN.value:

        if not data.partner_id:
            raise HTTPException(
                status_code=400,
                detail="partner_id required for admin"
            )

        partner = await db.get(
            Partner,
            data.partner_id
        )

        if not partner:
            raise HTTPException(
                status_code=404,
                detail="Partner not found"
            )

        partner_id = data.partner_id

    else:
        partner_id = current["user"].id

    result = await db.execute(
        select(Client).where(
            Client.email == data.email
        )
    )

    existing_client = result.scalar_one_or_none()

    if existing_client:
        raise HTTPException(
            status_code=400,
            detail="Client already exists"
        )

    client = Client(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash(
            data.password
        ),
        role="client",
        partner_id=partner_id,
        is_active=data.is_active
    )

    db.add(client)

    await db.commit()
    await db.refresh(client)

    await create_audit_log(
        db=db,
        actor=current,
        action="create",
        module="Client",
        table_name="clients",
        record_id=client.id,
        new_data=model_to_dict(client),
        description=f"Created client '{client.name}'.",
        status="success",
        request=request,
    )

    return client

async def get_my_clients_service(
    db,
    current,
    partner_id: int | None = None
):
    if current["role"] == UserRole.SUPER_ADMIN:

        if partner_id:

            result = await db.execute(
                select(Client).where(
                    Client.partner_id == partner_id
                )
            )

        else:

            result = await db.execute(
                select(Client)
            )

    else:

        result = await db.execute(
            select(Client).where(
                Client.partner_id ==
                current["user"].id
            )
        )

    return result.scalars().all()


# =====================================
# UPDATE CLIENT
# =====================================

async def update_client_service(
    db,
    client_id: int,
    data,
    current,
    request: Request,
):
    result = await db.execute(
        select(Client).where(
            Client.id == client_id
        )
    )

    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            404,
            "Client not found"
        )

    if current["role"] == UserRole.PARTNER.value:
        if client.partner_id != current["user"].id:
            raise HTTPException(
                403,
                "Not your client"
            )

    old_data = model_to_dict(client)

    if data.name is not None:
        client.name = data.name

    if data.email is not None:
        result = await db.execute(
            select(Client).where(
                Client.email == data.email,
                Client.id != client_id
            )
        )

        if result.scalar_one_or_none():
            raise HTTPException(
                400,
                "Email already exists"
            )

        client.email = data.email

    if data.is_active is not None:
        client.is_active = data.is_active

    await db.commit()
    await db.refresh(client)

    await create_audit_log(
        db=db,
        actor=current,
        action="update",
        module="Client",
        table_name="clients",
        record_id=client.id,
        old_data=old_data,
        new_data=model_to_dict(client),
        description=f"Updated client '{client.name}'.",
        status="success",
        request=request,
    )

    return client


# =====================================
# DEACTIVATE CLIENT
# =====================================

async def delete_client_service(
    db,
    client_id: int,
    current,
    request: Request,
):
    result = await db.execute(
        select(Client).where(
            Client.id == client_id
        )
    )

    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            404,
            "Client not found"
        )

    if current["role"] == UserRole.PARTNER.value:

        if client.partner_id != current["user"].id:
            raise HTTPException(
                403,
                "Not your client"
            )

    old_data = model_to_dict(client)
    client.is_active = False

    await db.commit()
    await db.refresh(client)

    await create_audit_log(
        db=db,
        actor=current,
        action="delete",
        module="Client",
        table_name="clients",
        record_id=client.id,
        old_data=old_data,
        new_data=None,
        description=f"Deleted client '{client.name}'.",
        status="success",
        request=request,
    )

    return {
        "message":
        "Client deactivated successfully"
    }


# =====================================
# ACTIVATE CLIENT
# =====================================

async def activate_client_service(
    db,
    client_id: int,
    current,
    request: Request,
):
    result = await db.execute(
        select(Client).where(
            Client.id == client_id
        )
    )

    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            404,
            "Client not found"
        )

    if current["role"] == UserRole.PARTNER.value:

        if client.partner_id != current["user"].id:
            raise HTTPException(
                403,
                "Not your client"
            )

    if client.is_active:
        raise HTTPException(
            400,
            "Client already active"
        )

    old_data = model_to_dict(client)
    client.is_active = True

    await db.commit()
    await db.refresh(client)

    await create_audit_log(
        db=db,
        actor=current,
        action="update",
        module="Client",
        table_name="clients",
        record_id=client.id,
        old_data=old_data,
        new_data=model_to_dict(client),
        description=f"Activated client '{client.name}'.",
        status="success",
        request=request,
    )

    return {
        "message":
        "Client activated successfully"
    }




async def partner_dashboard_service(
    db,
    current,
    partner_id: int | None = None
):

    if current["role"] == UserRole.SUPER_ADMIN.value:

        if partner_id:
            base_query = (
                select(Client)
                .where(Client.partner_id == partner_id)
            )
        else:
            base_query = select(Client)

    else:

        base_query = (
            select(Client)
            .where(
                Client.partner_id == current["user"].id
            )
        )

    # --------------------------
    # Total Clients
    # --------------------------

    total_clients = await db.scalar(
        select(func.count())
        .select_from(base_query.subquery())
    )

    # --------------------------
    # Active Clients
    # --------------------------

    active_query = base_query.where(
        Client.is_active == True
    )

    active_clients = await db.scalar(
        select(func.count())
        .select_from(active_query.subquery())
    )

    # --------------------------
    # Inactive Clients
    # --------------------------

    inactive_query = base_query.where(
        Client.is_active == False
    )

    inactive_clients = await db.scalar(
        select(func.count())
        .select_from(inactive_query.subquery())
    )

    # --------------------------
    # Last 7 Days
    # --------------------------

    seven_days = datetime.utcnow() - timedelta(days=7)

    new_query = base_query.where(
        Client.created_at >= seven_days
    )

    new_clients = await db.scalar(
        select(func.count())
        .select_from(new_query.subquery())
    )

    # --------------------------
    # Previous 7 Days
    # --------------------------

    previous_start = seven_days - timedelta(days=7)

    previous_query = base_query.where(
        Client.created_at >= previous_start,
        Client.created_at < seven_days
    )

    previous_clients = await db.scalar(
        select(func.count())
        .select_from(previous_query.subquery())
    )

    # --------------------------
    # Growth %
    # --------------------------

    if previous_clients == 0:

        growth = (
            100.0
            if new_clients > 0
            else 0.0
        )

    else:

        growth = round(
            (
                (new_clients - previous_clients)
                / previous_clients
            ) * 100,
            2
        )

    return {

        "total_clients": total_clients,

        "active_clients": active_clients,

        "inactive_clients": inactive_clients,

        "new_clients_last_7_days": new_clients,

        "growth_percentage": growth,

        "total_active": active_clients
    }