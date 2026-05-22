
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.api.routes import client
from app.accounts.client.model import Client
from app.db.config import SessionDep
from app.accounts.table.model import Table
from app.accounts.table.schema import TableCreate, TableUpdate, TableOut
from app.accounts.deps import require_client, require_roles, UserRole #, require_super_admin, require_client,
from app.accounts.deps import access_three, UserRole, access_four
router = APIRouter(prefix="/tables", tags=["Tables"])




# ✅ CREATE TABLE
from app.accounts.branch.model import Branch

@router.post("/create_table", response_model=TableOut)
async def create_table(
    data: TableCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    user = current["user"]

    # ✅ Get Branch
    result = await db.execute(
        select(Branch).where(
            Branch.id == data.branch_id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(404, "Branch not found")

    # ✅ Ownership Check
    if branch.client_id != user.id:
        raise HTTPException(403, "Not allowed")

    table = Table(
        client_id=branch.client_id,
        branch_id=branch.id,
        name=data.name,
        floor=data.floor,
        number_of_seats=data.number_of_seats,
        shape=data.shape
    )

    db.add(table)
    await db.commit()
    await db.refresh(table)
    return table



# ✅ GET ALL TABLES (BRANCH SCOPED)
@router.get("/see_table", response_model=list[TableOut])
async def get_tables(
    db: SessionDep,
    current=Depends(access_four),
    branch_id: int | None = None
):
    role = current["role"]
    user = current["user"]

    query = select(Table).join(
        Branch,
        Branch.id == Table.branch_id
    )

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        pass

    # ✅ PARTNER
    elif role == UserRole.PARTNER:
        query = query.join(
            Client,
            Client.id == Branch.client_id
        ).where(
            Client.partner_id == user.id
        )

    # ✅ CLIENT
    elif role == UserRole.CLIENT:
        query = query.where(
            Branch.client_id == user.id
        )

    # ✅ STAFF
    elif role == UserRole.STAFF:
        query = query.where(
            Table.branch_id == user.branch_id
        )

    else:
        raise HTTPException(403, "Not authorized")

    # ✅ Optional Branch Filter
    if branch_id:
        query = query.where(
            Table.branch_id == branch_id
        )

        # ✅ Staff Security
        if (
            role == UserRole.STAFF
            and branch_id != user.branch_id
        ):
            raise HTTPException(
                403,
                "Not allowed to access this branch"
            )

    result = await db.execute(query)

    return result.scalars().unique().all()





# ✅ UPDATE TABLE
@router.put("/{table_id}", response_model=TableOut)
async def update_table(
    table_id: int,
    data: TableUpdate,
    db: SessionDep,
    current=Depends(access_four)
):
    role = current["role"]
    user = current["user"]

    query = select(Table).join(
        Branch,
        Branch.id == Table.branch_id
    ).where(Table.id == table_id)

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        pass

    # ✅ PARTNER
    elif role == UserRole.PARTNER:
        query = query.join(
            Client,
            Client.id == Branch.client_id
        ).where(
            Client.partner_id == user.id
        )

    # ✅ CLIENT
    elif role == UserRole.CLIENT:
        query = query.where(
            Branch.client_id == user.id
        )

    # ✅ STAFF
    elif role == UserRole.STAFF:
        query = query.where(
            Table.branch_id == user.branch_id
        )

    else:
        raise HTTPException(403, "Not authorized")

    result = await db.execute(query)
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(
            status_code=404,
            detail="Table not found"
        )

    try:
        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(table, key, value)

        await db.commit()
        await db.refresh(table)

        return table

    except Exception as e:
        await db.rollback()
        print("UPDATE ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )




# ✅ DELETE TABLE (SOFT DELETE)
@router.delete("/{table_id}")
async def delete_table(
    table_id: int,
    db: SessionDep,
    current=Depends(access_three)
):
    role = current["role"]
    user = current["user"]

    query = select(Table).join(
        Branch,
        Branch.id == Table.branch_id
    ).where(Table.id == table_id)

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        pass

    # ✅ PARTNER
    elif role == UserRole.PARTNER:
        query = query.join(
            Client,
            Client.id == Branch.client_id
        ).where(
            Client.partner_id == user.id
        )

    # ✅ CLIENT
    elif role == UserRole.CLIENT:
        query = query.where(
            Branch.client_id == user.id
        )

    else:
        raise HTTPException(403, "Not authorized")

    result = await db.execute(query)
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(404, "Table not found")

    await db.delete(table)

    await db.commit()

    return {
        "success": True,
        "message": "Table deleted successfully"
    }



@router.post("/{table_id}/seat")
async def seat_table(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    role = current["role"]
    user = current["user"]

    query = select(Table).join(
        Branch,
        Branch.id == Table.branch_id
    ).where(Table.id == table_id)

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        pass

    # ✅ PARTNER
    elif role == UserRole.PARTNER:
        query = query.join(
            Client,
            Client.id == Branch.client_id
        ).where(
            Client.partner_id == user.id
        )

    # ✅ CLIENT
    elif role == UserRole.CLIENT:
        query = query.where(
            Branch.client_id == user.id
        )

    # ✅ STAFF
    elif role == UserRole.STAFF:
        query = query.where(
            Table.branch_id == user.branch_id
        )

    else:
        raise HTTPException(403, "Not authorized")

    result = await db.execute(query)
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(404, "Table not found")

    if table.status != "available":
        raise HTTPException(400, "Table not available")

    table.status = "occupied"

    await db.commit()

    return {
        "message": "Customer seated"
    }



@router.post("/{table_id}/vacate")
async def vacate_table(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    role = current["role"]
    user = current["user"]

    query = select(Table).join(
        Branch,
        Branch.id == Table.branch_id
    ).where(Table.id == table_id)

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        pass

    # ✅ PARTNER
    elif role == UserRole.PARTNER:
        query = query.join(
            Client,
            Client.id == Branch.client_id
        ).where(
            Client.partner_id == user.id
        )

    # ✅ CLIENT
    elif role == UserRole.CLIENT:
        query = query.where(
            Branch.client_id == user.id
        )

    # ✅ STAFF
    elif role == UserRole.STAFF:
        query = query.where(
            Table.branch_id == user.branch_id
        )

    else:
        raise HTTPException(403, "Not authorized")

    result = await db.execute(query)
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(404, "Table not found")

    table.status = "available"

    await db.commit()

    return {
        "message": "Table vacated"
    }



@router.get("/{table_id}/status")
async def get_table_status(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    role = current["role"]
    user = current["user"]

    query = (
        select(Table)
        .join(Branch, Branch.id == Table.branch_id)
        .where(Table.id == table_id)
    )

    if role == UserRole.CLIENT:
        query = query.where(
            Branch.client_id == user.id
        )

    elif role == UserRole.STAFF:
        query = query.where(
            Table.branch_id == user.branch_id
        )

    result = await db.execute(query)

    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(404, "Table not found")

    return {
        "table_id": table.id,
        "branch_id": table.branch_id,
        "status": table.status,
        "is_vacant": table.status == "available"
    }