# app/accounts/partner/service.py

from fastapi import HTTPException
from sqlalchemy import select
from passlib.context import CryptContext

from app.accounts.client.model import Client
from app.accounts.partner.model import Partner
from app.accounts.deps import UserRole

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
    current
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

    return client


# =====================================
# GET CLIENTS
# =====================================

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
    current
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

    if data.password is not None:
        client.password_hash = (
            pwd_context.hash(
                data.password
            )
        )

    if data.is_active is not None:
        client.is_active = data.is_active

    await db.commit()
    await db.refresh(client)

    return client


# =====================================
# DEACTIVATE CLIENT
# =====================================

async def delete_client_service(
    db,
    client_id: int,
    current
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

    client.is_active = False

    await db.commit()
    await db.refresh(client)

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
    current
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

    client.is_active = True

    await db.commit()
    await db.refresh(client)

    return {
        "message":
        "Client activated successfully"
    }