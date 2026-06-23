from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.category.model import Category
from app.accounts.category.schema import CategoryCreate
from app.accounts.deps import UserRole


class CategoryService:

    @staticmethod
    async def create_category(
        client_id: int,
        payload: CategoryCreate,
        db,
        current
    ):
        user = current["user"]
        role = current["role"]

        if role == UserRole.CLIENT:
            if user.id != client_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied"
                )

        elif role == UserRole.STAFF:
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

    @staticmethod
    async def get_categories(
        branch_id: int,
        db,
        current
    ):
        user = current["user"]
        role = current["role"]

        if role == UserRole.STAFF:
            if branch_id != user.branch_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied"
                )

        result = await db.execute(
            select(Category).where(
                Category.branch_id == branch_id
            )
        )

        return result.scalars().all()

    @staticmethod
    async def update_category(
        category_id: int,
        payload: CategoryCreate,
        db,
        current
    ):
        user = current["user"]
        role = current["role"]

        query = select(Category).where(
            Category.id == category_id
        )

        if role == UserRole.CLIENT:
            query = query.where(
                Category.client_id == user.id
            )

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

        category.name = payload.name
        category.icon = payload.icon

        await db.commit()
        await db.refresh(category)

        return category

    @staticmethod
    async def delete_category(
        category_id: int,
        db,
        current
    ):
        user = current["user"]
        role = current["role"]

        query = select(Category).where(
            Category.id == category_id
        )

        if role == UserRole.CLIENT:
            query = query.where(
                Category.client_id == user.id
            )

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

        await db.delete(category)
        await db.commit()

        return {
            "message": "Category deleted"
        }