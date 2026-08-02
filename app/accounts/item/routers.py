from fastapi import APIRouter, Depends, File, UploadFile

from app.accounts.deps import (
    access_four,
    get_current_user
)

from app.accounts.item.schema import (
    ItemCreate,
    ItemUpdate,
    ItemOut
)

from app.accounts.item.service import (
    get_items_service,
    create_item_service,
    update_item_service,
    delete_item_service,
    upload_image_service,
    update_image_service
)
from app.accounts.item.enum import FoodType, ItemSort

from app.db.config import SessionDep

router = APIRouter(
    prefix="/items",
    tags=["Items"]
)




@router.get("/get_items", response_model=list[ItemOut])
async def get_items(
    db: SessionDep,
    branch_id: int | None = None,
    limit: int | None = None,
    cursor: int | None = None,
    search: str | None = None,
    category_id: int |None = None,
    food_type: FoodType | None = None,
    sort_by: ItemSort | None = None,
    current=Depends(get_current_user),
):
    return await get_items_service(
        db=db,
        current=current,
        branch_id=branch_id,
        limit=limit,
        cursor=cursor,
        search=search,
        category_id=category_id,
        food_type=food_type,
        sort_by=sort_by,
    )

@router.post("/", response_model=ItemOut)
async def create_item(
    payload: ItemCreate,
    db: SessionDep,
    current=Depends(access_four)
):
    return await create_item_service(
        payload,
        db,
        current
    )


@router.put("/{item_id}", response_model=ItemOut)
async def update_item(
    item_id: int,
    payload: ItemUpdate,
    db: SessionDep,
    current=Depends(get_current_user)
):
    return await update_item_service(
        item_id,
        payload,
        db,
        current
    )


@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    return await delete_item_service(
        item_id,
        db,
        current
    )


@router.post("/{item_id}/upload-image")
async def upload_image(
    item_id: int,
    db: SessionDep,
    image: UploadFile = File(...)
):
    return await upload_image_service(
        item_id,
        image,
        db
    )


@router.put("/{item_id}/update-image")
async def update_image(
    item_id: int,
    db: SessionDep,
    image: UploadFile = File(...)
):
    return await update_image_service(
        item_id,
        image,
        db
    )