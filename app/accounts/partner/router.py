from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from passlib.context import CryptContext
from app.accounts.client.model import Client
from app.accounts.client.schema import ClientOut, ClientCreate, ClientUpdate
from app.db.config import SessionDep
from app.accounts.partner.model import Partner
from app.accounts.deps import UserRole, access_two, require_roles

router = APIRouter(prefix="/partner", tags=["Partner"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



# 🔥 Allow BOTH Partner + SuperAdmin
partner_access = require_roles(UserRole.PARTNER, UserRole.SUPER_ADMIN)


@router.post("/clients", response_model=ClientOut)
async def create_client(
    data: ClientCreate,
    db: SessionDep,
    current=Depends(access_two)
):
    # ✅ FIX: SuperAdmin must send partner_id in request body
    if current["role"] == UserRole.SUPER_ADMIN.value:
        if not hasattr(data, "partner_id") or not data.partner_id:
            raise HTTPException(400, "partner_id required for admin")

        # 🔥 check partner exists
        partner = await db.get(Partner, data.partner_id)
        if not partner:
            raise HTTPException(404, "Partner not found")

        partner_id = data.partner_id
    else:
        partner_id = current["user"].id

    # ✅ duplicate check
    result = await db.execute(
        select(Client).where(Client.email == data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Client already exists")

    client = Client(
        name=data.name,
        email=data.email,
        password_hash=pwd_context.hash(data.password),
        role="client",
        partner_id=partner_id,
        is_active=data.is_active
    )

    db.add(client)
    await db.commit()
    await db.refresh(client)

    return client


# ===========================
# ✅ GET MY CLIENTS
# ===========================
@router.get("/clients", response_model=list[ClientOut])
async def get_my_clients(
    db: SessionDep,
    current=Depends(access_two),
    partner_id: int | None = None
):
    # 🔐 SUPER ADMIN
    if current["role"] == UserRole.SUPER_ADMIN:
        
        # ✅ if partner_id given → filter
        if partner_id:
            result = await db.execute(
                select(Client).where(Client.partner_id == partner_id)
            )
        else:
            # ✅ NEW: return ALL clients
            result = await db.execute(select(Client))

    # 🔐 PARTNER → only own clients
    else:
        result = await db.execute(
            select(Client).where(
                Client.partner_id == current["user"].id
            )
        )

    return result.scalars().all()




@router.put("/clients/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    db: SessionDep,
    current=Depends(access_two)
):
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(404, "Client not found")

    # 🔐 FIX: Ownership strict
    # if current["role"] == UserRole.PARTNER.value:
    #     if client.partner_id != current["user"].id:
    #         raise HTTPException(403, "Not your client")

    if current["role"] == UserRole.PARTNER.value:
        result = await db.execute(
            select(Client).where(
                Client.id == client_id,
                Client.partner_id == current["user"].id
            )
        )
    
    else:
        result = await db.execute(
            select(Client).where(Client.id == client_id)
        )

    # ✅ update fields
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
            raise HTTPException(400, "Email already exists")

        client.email = data.email

    if data.password is not None:
        client.password_hash = pwd_context.hash(data.password)

    if data.is_active is not None:
        client.is_active = data.is_active

    await db.commit()
    await db.refresh(client)

    return client


# ===========================
# ✅ DELETE CLIENT
# ===========================
@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: int,
    db: SessionDep,
    current=Depends(access_two)
):
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # 🔐 Ownership check
    if current["role"] == UserRole.PARTNER.value:
        if client.partner_id != current["user"].id:
            raise HTTPException(status_code=403, detail="Not your client")

    # ✅ Soft delete (deactivate)
    client.is_active = False

    await db.commit()
    await db.refresh(client)

    return {"message": "Client deactivated successfully"}


@router.put("/clients/{client_id}/activate")
async def activate_client(
    client_id: int,
    db: SessionDep,
    current=Depends(access_two)
):
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # 🔐 Ownership check
    if current["role"] == UserRole.PARTNER.value:
        if client.partner_id != current["user"].id:
            raise HTTPException(status_code=403, detail="Not your client")

    # ⚠️ Already active check
    if client.is_active:
        raise HTTPException(status_code=400, detail="Client already active")

    # ✅ Activate
    client.is_active = True

    await db.commit()
    await db.refresh(client)

    return {"message": "Client activated successfully"}