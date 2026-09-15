# app/online_item_mappings/router.py

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_db

from app.accounts.online_item_mappings.schema import (
    OnlinePlatformItemMappingCreate,
    OnlinePlatformItemMappingUpdate,
    OnlinePlatformItemMappingOut,
    OnlinePlatformItemMappingListResponse,
)

from app.accounts.online_item_mappings.service import (
    OnlinePlatformItemMappingService,
)


router = APIRouter(
    prefix="/online-item-mappings",
    tags=["Online Platform Item Mappings"],
)


# ============================================================
# CREATE
# ============================================================

@router.post(
    "/",
    response_model=OnlinePlatformItemMappingOut,
    status_code=201,
)
async def create_item_mapping(
    data: OnlinePlatformItemMappingCreate,
    db: AsyncSession = Depends(get_db),
):

    service = OnlinePlatformItemMappingService(db)

    return await service.create(data)


# ============================================================
# LIST
# ============================================================

@router.get(
    "/",
    response_model=OnlinePlatformItemMappingListResponse,
)
async def list_item_mappings(
    connection_id: Optional[int] = Query(
        default=None,
        gt=0,
    ),

    item_id: Optional[int] = Query(
        default=None,
        gt=0,
    ),

    is_active: Optional[bool] = None,

    db: AsyncSession = Depends(get_db),
):

    service = OnlinePlatformItemMappingService(db)

    mappings, total = await service.list(
        connection_id=connection_id,
        item_id=item_id,
        is_active=is_active,
    )

    return {
        "items": mappings,
        "total": total,
    }


# ============================================================
# GET BY ID
# ============================================================

@router.get(
    "/{mapping_id}",
    response_model=OnlinePlatformItemMappingOut,
)
async def get_item_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
):

    service = OnlinePlatformItemMappingService(db)

    return await service.get_by_id(mapping_id)


# ============================================================
# UPDATE
# ============================================================

@router.patch(
    "/{mapping_id}",
    response_model=OnlinePlatformItemMappingOut,
)
async def update_item_mapping(
    mapping_id: int,
    data: OnlinePlatformItemMappingUpdate,
    db: AsyncSession = Depends(get_db),
):

    service = OnlinePlatformItemMappingService(db)

    return await service.update(
        mapping_id=mapping_id,
        data=data,
    )


# ============================================================
# DELETE
# ============================================================

@router.delete(
    "/{mapping_id}",
)
async def delete_item_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
):

    service = OnlinePlatformItemMappingService(db)

    return await service.delete(mapping_id)


# ============================================================
# RESOLVE PLATFORM ITEM
# ============================================================

@router.get(
    "/resolve/{connection_id}/{platform_item_id}",
    response_model=Optional[OnlinePlatformItemMappingOut],
)
async def resolve_platform_item(
    connection_id: int,
    platform_item_id: str,
    db: AsyncSession = Depends(get_db),
):

    service = OnlinePlatformItemMappingService(db)

    return await service.resolve_platform_item(
        connection_id=connection_id,
        platform_item_id=platform_item_id,
    )