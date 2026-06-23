from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from slugify import slugify

from app.accounts.brand.model import Brand
from app.accounts.brand.schema import (
    BrandCreate,
    BrandUpdate
)
from app.accounts.client.model import Client
from app.accounts.deps import (
    UserRole,
    get_client_if_accessible
)


class BrandService:

    @staticmethod
    async def create_brand(
        data: BrandCreate,
        db,
        current
    ):
        client = await get_client_if_accessible(
            client_id=data.client_id,
            db=db,
            current=current
        )

        slug = slugify(data.slug)

        result = await db.execute(
            select(Brand).where(
                Brand.slug == slug,
                Brand.client_id == client.id
            )
        )

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Brand slug already exists in this client"
            )

        brand = Brand(
            name=data.name,
            slug=slug,
            client_id=client.id
        )

        db.add(brand)

        await db.commit()
        await db.refresh(brand)

        return brand

    @staticmethod
    async def get_brands(
        db,
        current
    ):
        role = current["role"]
        user = current["user"]

        if role == UserRole.SUPER_ADMIN:

            query = select(Brand)

        elif role == UserRole.PARTNER:

            query = (
                select(Brand)
                .join(Brand.client)
                .where(
                    Client.partner_id == user.id
                )
            )

        elif role == UserRole.CLIENT:

            query = (
                select(Brand)
                .where(
                    Brand.client_id == user.id
                )
            )

        elif role == UserRole.STAFF:

            query = (
                select(Brand)
                .where(
                    Brand.client_id == user.client_id
                )
            )

        else:
            raise HTTPException(
                status_code=403,
                detail="Not allowed"
            )

        result = await db.execute(
            query.options(
                selectinload(Brand.client)
            )
        )

        return result.scalars().all()

    @staticmethod
    async def update_brand(
        brand_id: int,
        data: BrandUpdate,
        db,
        current
    ):
        result = await db.execute(
            select(Brand)
            .options(
                selectinload(Brand.client)
            )
            .where(
                Brand.id == brand_id
            )
        )

        brand = result.scalar_one_or_none()

        if not brand:
            raise HTTPException(
                status_code=404,
                detail="Brand not found"
            )

        await get_client_if_accessible(
            client_id=brand.client_id,
            db=db,
            current=current
        )

        if data.name:
            brand.name = data.name

        if data.slug:

            slug = slugify(data.slug)

            existing = await db.execute(
                select(Brand).where(
                    Brand.slug == slug,
                    Brand.client_id == brand.client_id,
                    Brand.id != brand_id
                )
            )

            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="Slug already exists"
                )

            brand.slug = slug

        await db.commit()
        await db.refresh(brand)

        return brand

    @staticmethod
    async def delete_brand(
        brand_id: int,
        db,
        current
    ):
        result = await db.execute(
            select(Brand)
            .options(
                selectinload(Brand.client)
            )
            .where(
                Brand.id == brand_id
            )
        )

        brand = result.scalar_one_or_none()

        if not brand:
            raise HTTPException(
                status_code=404,
                detail="Brand not found"
            )

        await get_client_if_accessible(
            client_id=brand.client_id,
            db=db,
            current=current
        )

        await db.delete(brand)

        await db.commit()

        return {
            "message": "Brand deleted"
        }