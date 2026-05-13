from sqlalchemy import select
from fastapi import APIRouter, Depends, Path, HTTPException
from app.accounts.staff.model import Staff
from app.accounts.category.model import Category
from app.accounts.category.schema import CategoryCreate, CategoryOut
from app.db.config import SessionDep
from app.accounts.client.model import Client
from app.accounts.deps import access_three, UserRole
from passlib.context import CryptContext
from slugify import slugify
from app.accounts.deps import get_current_user


router = APIRouter(
    prefix="/category",
    tags=["Category"]
)


@router.post("/create_cat/clients/{client_id}/categories", response_model=CategoryOut)
async def create_category(
    client_id: int,
    payload: CategoryCreate,
    db: SessionDep,
    current = Depends(get_current_user)
):
    if current is None:
        raise HTTPException(status_code=404, detail="User not found")

    # check client
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    category = Category(
        name=payload.name,
        icon=payload.icon,
        client_id=client_id,
        branch_id=payload.branch_id
    )

    db.add(category)

    await db.commit()
    await db.refresh(category)

    return category


@router.get("/clients/{client_id}/categories/get_cat", response_model=list[CategoryOut])
async def get_categories(client_id: int, db: SessionDep,current = Depends(get_current_user)):
    
    if current is None:
        raise HTTPException (status_code=404, detail="User not found")

    result = await db.execute(
        select(Category).where(Category.client_id == client_id)
    )
    categories = result.scalars().all()

    return categories



# @router.get("/categories/{category_id}", response_model=CategoryOut)
# async def get_category(category_id: int, db: SessionDep, current = Depends(get_current_user)):
#     if current is None:
#         raise HTTPException (status_code=404, detail="User not found")
#     result = await db.execute(
#         select(Category).where(Category.id == category_id)
#     )
#     category = result.scalar_one_or_none()

#     if not category:
#         raise HTTPException(status_code=404, detail="Category not found")

#     return category



@router.put("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    payload: CategoryCreate,
    db: SessionDep,
    current = Depends(get_current_user)
):  
    if current is None:
        raise HTTPException(status_code=404,detail="User not found")
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.name = payload.name
    category.icon = payload.icon

    await db.commit()
    await db.refresh(category)

    return category



@router.delete("/categories/{category_id}")
async def delete_category(category_id: int, db: SessionDep,current= Depends(get_current_user)):

    if current is None:
        raise HTTPException (status_code=404, detail="User not found")
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    await db.delete(category)
    await db.commit()

    return {"message": "Category deleted"}


