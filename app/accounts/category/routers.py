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
        raise HTTPException(status_code=404, detail="User not found")

    user = current["user"]
    role = current["role"]

    # ✅ CLIENT SECURITY
    if role == UserRole.CLIENT:

        # user.id = client.id
        if user.id != client_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

    # ✅ STAFF SECURITY
    elif role == UserRole.STAFF:

        # staff has client_id
        if user.client_id != client_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        if payload.branch_id != user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Invalid branch access"
            )

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

    user = current["user"]
    role = current["role"]

    # STAFF SECURITY
    if role == UserRole.STAFF:

        if branch_id != user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

    query = select(Category).where(
        Category.branch_id == branch_id
    )

    result = await db.execute(query)

    categories = result.scalars().all()

    return categories



@router.put("/categories/{category_id}", response_model=CategoryOut)
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

    user = current["user"]
    role = current["role"]

    query = select(Category).where(
        Category.id == category_id
    )

    # ✅ CLIENT
    if role == UserRole.CLIENT:

        query = query.where(
            Category.client_id == user.id
        )

    # ✅ STAFF
    elif role == UserRole.STAFF:

        query = query.where(
            Category.branch_id == user.branch_id
        )

    result = await db.execute(query)

    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    # ✅ Update allowed fields
    category.name = payload.name
    category.icon = payload.icon

    await db.commit()
    await db.refresh(category)

    return category


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

    user = current["user"]
    role = current["role"]

    query = select(Category).where(
        Category.id == category_id
    )

    # ✅ CLIENT
    if role == UserRole.CLIENT:

        query = query.where(
            Category.client_id == user.id
        )

    # ✅ STAFF
    elif role == UserRole.STAFF:

        query = query.where(
            Category.branch_id == user.branch_id
        )

    # ✅ PARTNER / SUPER ADMIN
    else:
        pass

    result = await db.execute(query)

    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    await db.delete(category)
    await db.commit()

    return {
        "message": "Category deleted"
    }