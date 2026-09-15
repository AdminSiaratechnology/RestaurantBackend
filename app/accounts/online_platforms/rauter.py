# app/online_platforms/router.py

from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
)

from sqlalchemy import select

from app.db.config import SessionDep
from app.accounts.online_platforms.model import OnlinePlatformConnection
from app.accounts.online_platforms.schema import (
    OnlinePlatformConnectionCreate,
    OnlinePlatformConnectionListResponse,
    OnlinePlatformConnectionOut,
    OnlinePlatformConnectionUpdate,
)
from app.accounts.online_platforms.service import (
    OnlinePlatformConnectionService,
)


router = APIRouter(
    prefix="/online-platforms",
    tags=["Online Platforms"],
)


# =========================================================
# CREATE
# =========================================================

@router.post(
    "/",
    response_model=OnlinePlatformConnectionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_online_platform_connection(
    payload: OnlinePlatformConnectionCreate,
    db: SessionDep,
):

    try:
        connection = await OnlinePlatformConnectionService.create(
            db=db,
            data=payload,
        )

        return connection

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# =========================================================
# LIST
# =========================================================

@router.get(
    "/",
    response_model=OnlinePlatformConnectionListResponse,
)
async def list_online_platform_connections(
    db: SessionDep,
    branch_id: Optional[int] = Query(
        default=None,
        gt=0,
    ),
    platform: Optional[str] = Query(
        default=None,
    ),
    is_active: Optional[bool] = Query(
        default=None,
    ),
):

    if platform:
        platform = platform.strip().lower()

    items = await OnlinePlatformConnectionService.list(
        db=db,
        branch_id=branch_id,
        platform=platform,
        is_active=is_active,
    )

    return {
        "items": items,
        "total": len(items),
    }


# =========================================================
# GET BY ID
# =========================================================

@router.get(
    "/{connection_id}",
    response_model=OnlinePlatformConnectionOut,
)
async def get_online_platform_connection(
    connection_id: int,
    db: SessionDep,
):

    connection = await OnlinePlatformConnectionService.get_by_id(
        db=db,
        connection_id=connection_id,
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Online platform connection not found",
        )

    return connection


# =========================================================
# UPDATE
# =========================================================

@router.patch(
    "/{connection_id}",
    response_model=OnlinePlatformConnectionOut,
)
async def update_online_platform_connection(
    connection_id: int,
    payload: OnlinePlatformConnectionUpdate,
    db: SessionDep,
):

    connection = await OnlinePlatformConnectionService.get_by_id(
        db=db,
        connection_id=connection_id,
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Online platform connection not found",
        )

    try:
        connection = (
            await OnlinePlatformConnectionService.update(
                db=db,
                connection=connection,
                data=payload,
            )
        )

        return connection

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# =========================================================
# DELETE
# =========================================================

@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_online_platform_connection(
    connection_id: int,
    db: SessionDep,
):

    connection = await OnlinePlatformConnectionService.get_by_id(
        db=db,
        connection_id=connection_id,
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Online platform connection not found",
        )

    await OnlinePlatformConnectionService.delete(
        db=db,
        connection=connection,
    )

    return None