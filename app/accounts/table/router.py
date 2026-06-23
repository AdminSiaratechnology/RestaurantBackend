# app/accounts/table/routers.py

from sqlalchemy import select, func

from app.accounts.branch.model import Branch
from app.accounts.table.model import Table, TableStatus


from fastapi import APIRouter, Depends

from app.db.config import SessionDep
from app.accounts.deps import (
    require_client,
    access_three,
    access_four
)

from app.accounts.table.schema import (
    TableCreate,
    TableUpdate,
    TableOut,
    TableStatus,
    TableStatusUpdate
)

from app.accounts.table.service import TableService

router = APIRouter(
    prefix="/tables",
    tags=["Tables"]
)


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
    filter_status: TableStatus | None = None
):
    return await TableService.get_tables(
        db,
        current["role"],
        current["user"],
        branch_id,
        filter_status
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


# app/accounts/table/routers.py

@router.get("/dashboard/all-branches")
async def table_dashboard_all_branches(
    db: SessionDep,
    current=Depends(require_client)
):
    return await TableService.table_dashboard_all_branches(
        db=db,
        client_id=current["user"].id
    )

@router.get(
    "/all-branches",
    operation_id="table_dashboard_all_branches_v1"
)
async def table_dashboard_all_branches(
    db: SessionDep,
    current=Depends(access_four)
):
    return await TableService.table_dashboard_all_branches(
        db=db,
        client_id=current["user"].id
    )