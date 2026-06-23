from fastapi import APIRouter, Depends, HTTPException

from app.accounts.category.schema import (
    CategoryCreate,
    CategoryOut
)
from app.accounts.category.service import CategoryService
from app.accounts.deps import get_current_user
from app.db.config import SessionDep

router = APIRouter(
    prefix="/category",
    tags=["Category"]
)


@router.post(
    "/create_cat/clients/{client_id}/categories",
    response_model=CategoryOut
)
async def create_category(
    client_id: int,
    payload: CategoryCreate,
    db: SessionDep,
    current=Depends(get_current_user)
):
    if current is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return await CategoryService.create_category(
        client_id=client_id,
        payload=payload,
        db=db,
        current=current
    )


@router.get(
    "/branches/{branch_id}/categories",
    response_model=list[CategoryOut]
)
async def get_categories(
    branch_id: int,
    db: SessionDep,
    current=Depends(get_current_user)
):
    if current is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return await CategoryService.get_categories(
        branch_id=branch_id,
        db=db,
        current=current
    )


@router.put(
    "/categories/{category_id}",
    response_model=CategoryOut
)
async def update_category(
    category_id: int,
    payload: CategoryCreate,
    db: SessionDep,
    current=Depends(get_current_user)
):
    if current is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return await CategoryService.update_category(
        category_id=category_id,
        payload=payload,
        db=db,
        current=current
    )


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: SessionDep,
    current=Depends(get_current_user)
):
    if current is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return await CategoryService.delete_category(
        category_id=category_id,
        db=db,
        current=current
    )