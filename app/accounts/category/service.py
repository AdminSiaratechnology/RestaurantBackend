from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.category.model import Category
from app.accounts.category.schema import CategoryCreate
from app.accounts.deps import UserRole
from app.core.cache import Cache
from fastapi.encoders import jsonable_encoder


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

        # Invalidate cache
        await Cache.delete(f"categories:branch:{payload.branch_id}")
        await Cache.delete(f"menu:branch:{payload.branch_id}")

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

        cache_key = f"categories:branch:{branch_id}"
        cached_data = await Cache.get(cache_key)
        if cached_data:
            return cached_data

        result = await db.execute(
            select(Category).where(
                Category.branch_id == branch_id
            )
        )
        
        categories = result.scalars().all()
        await Cache.set(cache_key, jsonable_encoder(categories), expire=1800)

        return categories

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

        await Cache.delete(f"categories:branch:{category.branch_id}")
        await Cache.delete(f"menu:branch:{category.branch_id}")

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

        branch_id = category.branch_id
        await db.delete(category)
        await db.commit()

        await Cache.delete(f"categories:branch:{branch_id}")
        await Cache.delete(f"menu:branch:{branch_id}")

        return {
            "message": "Category deleted"
        }