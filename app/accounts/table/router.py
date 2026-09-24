# app/accounts/table/routers.py

from sqlalchemy import select, func

from app.accounts.table.model import Table
from app.accounts.table.enum import TableStatus


from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer

from app.db.config import SessionDep
from app.accounts.deps import (
    require_client,
    access_three,
    access_four
)

from app.accounts.table.schema import (
    TableCreate,
    TableDetailsOut,
    TableUpdate,
    TableOut,
    TableStatus,
    TableStatusUpdate,
    TableLayoutUpdate,
    TableFloorUpdate,
)

from app.accounts.table.service import TableService

router = APIRouter(
    prefix="/tables",
    tags=["Tables"]
)

security_optional = HTTPBearer(auto_error=False)


@router.post(
    "/create_table",
    response_model=TableOut
)
async def create_table(
    data: TableCreate,
    db: SessionDep,
    current=Depends(require_client)
):
    return await TableService.create_table(
        db,
        data,
        current["user"]
    )


@router.get(
    "/see_table",
    response_model=list[TableOut]
)
async def get_tables(
    db: SessionDep,
    current=Depends(access_four),
    branch_id: int | None = None,
    filter_status: TableStatus | None = None,
    client_id: int | None = None,
    brand_id: int | None = None,
):
    return await TableService.get_tables(
        db,
        current["role"],
        current["user"],
        branch_id,
        filter_status
    )


@router.get(
    "/dashboard/all-branches"
)
async def table_dashboard_all_branches_client(
    db: SessionDep,
    current=Depends(require_client)
):
    return await TableService.table_dashboard_all_branches(
        db=db,
        client_id=current["user"].id
    )


# ── Floor Layout Endpoints ─────────────────────────────────────────────────────

@router.get(
    "/floors",
    response_model=list[str],
    summary="Get unique floor names for a branch",
    description=(
        "Returns the distinct set of floor strings from active tables in the branch. "
        "These are derived from the Table.floor field — no separate Floor model exists. "
        "Respects the same branch isolation rules as GET /tables/see_table."
    ),
)
async def get_floors(
    db: SessionDep,
    current=Depends(access_four),
    branch_id: int | None = None,
    client_id: int | None = None,
    brand_id: int | None = None,
):
    return await TableService.get_floors(
        db=db,
        role=current["role"],
        user=current["user"],
        branch_id=branch_id,
    )


@router.get(
    "/{table_id}",
    response_model=TableOut
)
async def get_table_by_id(
    table_id: int,
    db: SessionDep,
    credentials=Depends(security_optional)
):
    current = None
    if credentials and credentials.credentials:
        try:
            from app.accounts.deps import get_current_user
            current = await get_current_user(db, credentials)
        except Exception:
            current = None

    if current:
        return await TableService.get_table_by_id(
            db,
            table_id,
            current["role"],
            current["user"]
        )
    else:
        return await TableService.get_table_by_id(
            db,
            table_id
        )


@router.get(
    "/{table_id}/availability"
)
async def get_table_availability(
    table_id: int,
    db: SessionDep
):
    return await TableService.get_table_availability(
        db=db,
        table_id=table_id
    )


@router.get(
    "/{table_id}/details",
    response_model=TableDetailsOut
)
async def get_table_details(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    return await TableService.get_table_details(
        db=db,
        table_id=table_id,
        role=current["role"],
        user=current["user"]
    )


@router.put(
    "/{table_id}",
    response_model=TableOut
)
async def update_table(
    table_id: int,
    data: TableUpdate,
    db: SessionDep,
    current=Depends(access_four)
):
    table = await TableService.get_table_by_id(
        db,
        table_id,
        current["role"],
        current["user"]
    )

    return await TableService.update_table(
        db,
        table,
        data
    )


@router.delete("/{table_id}")
async def delete_table(
    table_id: int,
    db: SessionDep,
    current=Depends(access_three)
):
    table = await TableService.get_table_by_id(
        db,
        table_id,
        current["role"],
        current["user"]
    )

    return await TableService.delete_table(
        db,
        table
    )


@router.post("/{table_id}/seat")
async def seat_table(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    table = await TableService.get_table_by_id(
        db,
        table_id,
        current["role"],
        current["user"]
    )

    return await TableService.seat_table(
        db,
        table
    )


@router.post("/{table_id}/vacate")
async def vacate_table(
    table_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    table = await TableService.get_table_by_id(
        db,
        table_id,
        current["role"],
        current["user"]
    )

    return await TableService.vacate_table(
        db,
        table
    )


@router.patch(
    "/{table_id}/status",
    response_model=TableOut
)
async def update_table_status(
    table_id: int,
    data: TableStatusUpdate,
    db: SessionDep,
    current=Depends(access_four)
):
    table = await TableService.get_table_by_id(
        db,
        table_id,
        current["role"],
        current["user"]
    )

    return await TableService.update_status(
        db,
        table,
        data.status
    )


# ── Floor Layout Endpoints ─────────────────────────────────────────────────────


@router.patch(
    "/{table_id}/layout",
    response_model=TableOut,
    summary="Update table canvas layout position",
    description=(
        "Persists the table's visual position (pos_x, pos_y), rotation, and "
        "optional display size (layout_width, layout_height) on the floor canvas. "
        "This endpoint ONLY affects the visual layout — it has zero effect on "
        "orders, billing, QR codes, sessions, or table status."
    ),
)
async def update_table_layout(
    table_id: int,
    data: TableLayoutUpdate,
    db: SessionDep,
    current=Depends(access_four),
):
    # get_table_by_id enforces branch isolation via build_table_query
    table = await TableService.get_table_by_id(
        db,
        table_id,
        current["role"],
        current["user"],
    )

    return await TableService.update_layout(
        db,
        table,
        data,
    )


@router.patch(
    "/{table_id}/floor",
    response_model=TableOut,
    summary="Update table floor assignment and layout position",
    description=(
        "Atomically updates a table's floor assignment and optional (pos_x, pos_y) layout position. "
        "Respects branch isolation and has zero side-effects on active orders, bills, QR codes, or sessions."
    ),
)
async def update_table_floor(
    table_id: int,
    data: TableFloorUpdate,
    db: SessionDep,
    current=Depends(access_four),
):
    table = await TableService.get_table_by_id(
        db,
        table_id,
        current["role"],
        current["user"],
    )

    return await TableService.update_floor(
        db,
        table,
        data,
    )
