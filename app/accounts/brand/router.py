from fastapi import APIRouter, Depends

from app.accounts.brand.schema import (
    BrandCreate,
    BrandOut,
    BrandUpdate
)
from app.accounts.brand.service import BrandService
from app.accounts.deps import (
    access_one,
    access_three
)
from app.db.config import SessionDep

router = APIRouter(
    prefix="/brand",
    tags=["Brand"]
)


@router.post(
    "/post",
    response_model=BrandOut
)
async def create_brand(
    data: BrandCreate,
    db: SessionDep,
    current=Depends(access_three)
):
    return await BrandService.create_brand(
        data=data,
        db=db,
        current=current
    )


@router.get(
    "/all_brand",
    response_model=list[BrandOut]
)
async def get_brands(
    db: SessionDep,
    current=Depends(access_one)
):
    return await BrandService.get_brands(
        db=db,
        current=current
    )


@router.put(
    "/update/{brand_id}",
    response_model=BrandOut
)
async def update_brand(
    brand_id: int,
    data: BrandUpdate,
    db: SessionDep,
    current=Depends(access_three)
):
    return await BrandService.update_brand(
        brand_id=brand_id,
        data=data,
        db=db,
        current=current
    )


@router.delete("/delete/{brand_id}")
async def delete_brand(
    brand_id: int,
    db: SessionDep,
    current=Depends(access_three)
):
    return await BrandService.delete_brand(
        brand_id=brand_id,
        db=db,
        current=current
    )