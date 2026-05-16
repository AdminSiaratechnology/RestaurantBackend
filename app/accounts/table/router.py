
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
    try:
        user = current["user"]

        # ✅ Get branch
        branch_result = await db.execute(
            select(Branch).where(Branch.id == data.branch_id)
        )
        branch = branch_result.scalar_one_or_none()

        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")

        # ✅ Ownership check (FIXED)
        if branch.client_id != user.id:
            raise HTTPException(status_code=403, detail="Not allowed")

        # ✅ Set client_id from DB (NOT request)
        data.client_id = branch.client_id

        table = Table(**data.dict())

        db.add(table)
        await db.commit()
        await db.refresh(table)

        return table

    except HTTPException as e:
        raise e

    except Exception as e:
        await db.rollback()
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    


# ✅ GET ALL TABLES (BRANCH SCOPED)
@router.get("/see_table", response_model=list[TableOut])
async def get_tables(
    db: SessionDep,
    current=Depends(access_four),
    branch_id: int | None = None
):
    role = current["role"]
    user = current["user"]
    query = (
        select(Table)
        .join(Branch, Branch.id == Table.branch_id)
    )

    # ✅ SUPER ADMIN
    if role == UserRole.SUPER_ADMIN:
        pass

    # ✅ PARTNER
    elif role == UserRole.PARTNER:
        query = query.join(Client, Client.id == Branch.client_id).where(
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

    # ✅ MAIN FIX → FILTER BY BRANCH
    if branch_id:
        query = query.where(
            Table.branch_id == branch_id
        )

        # ✅ STAFF SECURITY
        if role == UserRole.STAFF and branch_id != user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Not allowed to access this branch"
            )

    result = await db.execute(query)

    return result.scalars().unique().all()


# ✅ UPDATE TABLE
@router.put("/clients/{client_id}/tables/{table_id}", response_model=TableOut)
async def update_table(
    client_id: int,
    table_id: int,
    data: TableUpdate,
    db: SessionDep,
    current=Depends(require_client)
):
    admin = current["user"]

    # ✅ Check client belongs to admin
    client_result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.admin_id == admin.id
        )
    )
    client = client_result.scalar_one_or_none()

    if not client:
        raise HTTPException(403, "Not allowed")

    # ✅ Get table inside client
    result = await db.execute(
        select(Table).where(
            Table.id == table_id,
            Table.client_id == client_id
        )
    )
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(404, "Table not found")

    # ✅ Update
    for key, value in data.dict(exclude_unset=True).items():
        setattr(table, key, value)

    await db.commit()
    await db.refresh(table)

    return table


# ✅ DELETE TABLE (SOFT DELETE)
@router.delete("/clients/{client_id}/tables/{table_id}/deletetable")
async def delete_table(
    client_id: int,
    table_id: int,
    db: SessionDep,
    current=Depends(require_client)
):
    try:
        user = current["user"]

        result = await db.execute(
            select(Table)
            .join(Client, Client.id == Table.client_id)
            .where(
                Table.id == table_id,
                Table.client_id == client_id,
                Client.admin_id == user.id
            )
        )
        table = result.scalar_one_or_none()

        if not table:
            raise HTTPException(status_code=404, detail="Table not found or access denied")

        if not table.is_active:
            raise HTTPException(status_code=400, detail="Table already deleted")

        # ✅ Delete
        await db.delete(table)
        await db.commit()

        return {
            "success": True,
            "message": "Table deleted successfully"
        }

    except HTTPException as e:
        # ✅ Let FastAPI handle expected errors
        raise e

    except Exception as e:
        # ❌ Rollback if something fails
        await db.rollback()

        # Optional: print for debugging
        print("ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )



@router.post("/clients/{client_id}/tables/{table_id}/vacate")
async def vacate_table(
    client_id: int,
    table_id: int,
    db: SessionDep,
    current=Depends(require_client)
):
    client = current["user"]

    # ✅ Validate client
    client_result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.client_id == client.id
        )
    )
    client = client_result.scalar_one_or_none()

    if not client:
        raise HTTPException(403, "Not allowed")

    # ✅ Get table
    result = await db.execute(
        select(Table).where(
            Table.id == table_id,
            Table.client_id == client_id
        )
    )
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(404, "Table not found")

    table.status = "available"
    await db.commit()

    return {"message": "Table vacated"}



@router.post("/clients/{client_id}/tables/{table_id}/seat")
async def seat_table(
    client_id: int,
    table_id: int,
    db: SessionDep,
    current=Depends(require_client)
):
    user = current["user"]

    # # ✅ Validate client
    # client_result = await db.execute(
    #     select(Client).where(
    #         Client.id == client_id,
    #         Client.client_id == user.id   # 🔥 FIX HERE
    #     )
    # )
    # client = client_result.scalar_one_or_none()

    # if not client:
    #     raise HTTPException(403, "Not allowed")

    # 🔍 Get table WITH client filter
    result = await db.execute(
        select(Table).where(
            Table.id == table_id,
            Table.client_id == client_id
        )
    )
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(404, "Table not found")

    # ⚠️ Status check
    if table.status != "available":
        raise HTTPException(400, "Table not available")

    # ✅ Update status
    table.status = "occupied"
    await db.commit()

    return {"message": "Customer seated"}



@router.get("/clients/{client_id}/tables/{table_id}/status")
async def get_table_status(
    client_id: int,
    table_id: int,
    db: SessionDep,
):
    # 🔍 Get table with client filter
    result = await db.execute(
        select(Table).where(
            Table.id == table_id,
            Table.client_id == client_id
        )
    )
    table = result.scalar_one_or_none()

    if not table:
        raise HTTPException(404, "Table not found")

    return {
        "table_id": table.id,
        "client_id": table.client_id,
        "status": table.status,  # "available" or "occupied"
        "is_vacant": table.status == "available"
    }
