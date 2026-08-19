from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy import select, asc, desc
from app.accounts.pricing.model import Pricing
from app.accounts.item.enum import ItemSort
from app.accounts.branch.model import Branch
from app.accounts.category.model import Category
from app.accounts.deps import get_client_if_accessible
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing
from app.core.cache import Cache
from fastapi.encoders import jsonable_encoder
from app.accounts.item.enum import FoodType
from pathlib import Path
from uuid import uuid4

from app.accounts.item.schema import ItemOut
from app.core.s3 import (
    upload_file_to_s3,
    delete_file_from_s3,
    get_s3_object_key,
)

async def get_items_service(
    db,
    current,
    branch_id=None,
    limit=None,
    cursor=None,
    search=None,
    category_id=None,
    food_type: FoodType | None = None,
    sort_by: ItemSort | None = None,
):
    role = current["role"]
    user = current["user"]

    # =====================================================
    # GET BRANCH
    # =====================================================

    if role == "staff":
        final_branch_id = getattr(user, "selected_branch_id", None) or getattr(user, "branch_id", None)

        if not final_branch_id:
            raise HTTPException(
                status_code=400,
                detail="Staff branch not assigned"
            )

    elif role in ("client", "partner", "super_admin"):
        final_branch_id = branch_id or getattr(user, "branch_id", None)

        if not final_branch_id:
            raise HTTPException(
                status_code=400,
                detail="branch_id is required"
            )

    else:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    # =====================================================
    # VERIFY BRANCH
    # =====================================================

    result = await db.execute(
        select(Branch).where(
            Branch.id == final_branch_id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found"
        )

    # =====================================================
    # CACHE
    # =====================================================

    cache_key = (
        f"products:branch:{final_branch_id}:"
        f"{limit}:{cursor}:{search}:"
        f"{category_id}:{food_type}:{sort_by}"
    )

    cached_data = await Cache.get(cache_key)

    if cached_data is not None:
        return cached_data

    # =====================================================
    # QUERY
    # =====================================================

    query = (
        select(Item)
        .join(
            Pricing,
            (Pricing.item_id == Item.id)
            & (Pricing.branch_id == final_branch_id)
            & (Pricing.is_active.is_(True))
        )
        .options(
            selectinload(Item.pricings)
        )
        .where(
            Item.branch_id == final_branch_id,
            Item.is_active.is_(True),
        )
        .distinct()
    )

    # =====================================================
    # CATEGORY FILTER
    # =====================================================

    if category_id:
        query = query.where(
            Item.category_id == category_id
        )

    # =====================================================
    # SEARCH
    # =====================================================

    if search:
        query = query.where(
            Item.name.ilike(f"%{search}%")
        )

    # =====================================================
    # FOOD TYPE FILTER
    # =====================================================

    if food_type:
        query = query.where(
            Item.food_type == food_type
        )

    # =====================================================
    # CURSOR PAGINATION
    # =====================================================

    if cursor:
        query = query.where(
            Item.id > cursor
        )

    # =====================================================
    # SORTING
    # =====================================================

    if sort_by == ItemSort.high_to_low:
        query = query.order_by(
            desc(Pricing.price),
            Item.id.asc()
        )

    elif sort_by == ItemSort.low_to_high:
        query = query.order_by(
            asc(Pricing.price),
            Item.id.asc()
        )

    else:
        query = query.order_by(
            Item.id.asc()
        )

    # =====================================================
    # LIMIT
    # =====================================================

    if limit:
        query = query.limit(limit)

    # =====================================================
    # EXECUTE
    # =====================================================

    result = await db.execute(query)

    items = result.scalars().unique().all()

    # =====================================================
    # CACHE
    # =====================================================

    items_out = [ItemOut.model_validate(item).model_dump(mode="json") for item in items]

    await Cache.set(
        cache_key,
        items_out,
        expire=600
    )

    return items


async def create_item_service(
    payload,
    db,
    current,
    branch_id: int,
    client_id: int | None = None,
):
    effective_client_id = client_id or getattr(payload, "client_id", None)

    if not effective_client_id:
        raise HTTPException(
            status_code=400,
            detail="client_id is required"
        )

    if not branch_id:
        raise HTTPException(
            status_code=400,
            detail="branch_id is required"
        )

    client = await get_client_if_accessible(
        client_id=effective_client_id,
        db=db,
        current=current
    )

    if payload.category_id:
        result = await db.execute(
            select(Category).where(
                Category.id == payload.category_id,
                Category.client_id == client.id
            )
        )

        category = result.scalar_one_or_none()

        if not category or category.branch_id != branch_id:
            raise HTTPException(400, "Invalid category for this branch")

    result = await db.execute(
        select(Branch).where(
            Branch.id == branch_id,
            Branch.client_id == client.id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(400, "Invalid branch")

    result = await db.execute(
        select(Item).where(
            Item.name == payload.name,
            Item.branch_id == branch_id,
            Item.client_id == client.id
        )
    )

    if result.scalar_one_or_none():
        raise HTTPException(
            400,
            "Item already exists in this branch"
        )

    item_food_type = getattr(payload, "food_type", None) or FoodType.veg

    item = Item(
        name=payload.name,
        client_id=client.id,
        category_id=payload.category_id,
        branch_id=branch_id,
        image=payload.image_url,
        is_active=payload.is_active if payload.is_active is not None else True,
        food_type=item_food_type,
    )

    db.add(item)
    await db.flush()

    if payload.price is not None:
        pricing = Pricing(
            item_id=item.id,
            client_id=client.id,
            branch_id=branch_id,
            price=payload.price,
            is_active=(
                payload.pricing_is_active
                if payload.pricing_is_active is not None
                else True
            )
        )
        db.add(pricing)

    await db.commit()

    result = await db.execute(
        select(Item)
        .options(selectinload(Item.pricings))
        .where(Item.id == item.id)
    )

    await Cache.clear_menu_cache(branch_id, client.id)

    return result.scalar_one()


async def update_item_service(
    item_id,
    payload,
    db,
    current
):
    item = await db.get(Item, item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    await get_client_if_accessible(
        client_id=item.client_id,
        db=db,
        current=current
    )

    if payload.category_id:
        result = await db.execute(
            select(Category).where(
                Category.id == payload.category_id,
                Category.client_id == item.client_id
            )
        )
        category = result.scalar_one_or_none()
        if not category or category.branch_id != item.branch_id:
            raise HTTPException(400, "Invalid category for this branch")

    if payload.name:
        result = await db.execute(
            select(Item).where(
                Item.name == payload.name,
                Item.client_id == item.client_id,
                Item.branch_id == item.branch_id,
                Item.id != item_id
            )
        )

        if result.scalar_one_or_none():
            raise HTTPException(
                400,
                "Item already exists in this branch"
            )

    item_data = payload.model_dump(
        exclude_unset=True,
        exclude={"price", "pricing_is_active"}
    )

    for key, value in item_data.items():
        setattr(item, key, value)

    if payload.price is not None or payload.pricing_is_active is not None:

        result = await db.execute(
            select(Pricing).where(
                Pricing.item_id == item.id,
                Pricing.branch_id == item.branch_id
            )
        )

        pricing = result.scalar_one_or_none()

        if not pricing and payload.price is not None:
            pricing = Pricing(
                item_id=item.id,
                client_id=item.client_id,
                branch_id=item.branch_id,
                price=payload.price,
                is_active=(
                    payload.pricing_is_active
                    if payload.pricing_is_active is not None
                    else True
                )
            )

            db.add(pricing)

        else:
            if payload.price is not None:
                pricing.price = payload.price

            if payload.pricing_is_active is not None:
                pricing.is_active = payload.pricing_is_active

    await db.commit()

    result = await db.execute(
        select(Item)
        .options(selectinload(Item.pricings))
        .where(Item.id == item.id)
    )

    await Cache.clear_menu_cache(item.branch_id, item.client_id)

    return result.scalar_one()


async def delete_item_service(
    item_id,
    db,
    current
):
    item = await db.get(Item, item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    await get_client_if_accessible(
        client_id=item.client_id,
        db=db,
        current=current
    )

    branch_id = item.branch_id
    client_id = item.client_id

    await db.delete(item)
    await db.commit()

    await Cache.clear_menu_cache(branch_id, client_id)

    return {"message": "Item deleted"}




# ============================================================
# UPLOAD ITEM IMAGE
# ============================================================

async def upload_image_service(
    item_id: int,
    image: UploadFile,
    db,
):

    # --------------------------------------------------------
    # FIND ITEM
    # --------------------------------------------------------

    item = await db.get(
        Item,
        item_id,
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    # --------------------------------------------------------
    # FILE EXTENSION
    # --------------------------------------------------------

    extension = Path(
        image.filename or ""
    ).suffix.lower()

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    if extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG and WEBP "
                "images are allowed"
            ),
        )

    # --------------------------------------------------------
    # UNIQUE FILE NAME
    # --------------------------------------------------------

    filename = (
        f"{uuid4()}"
        f"{extension}"
    )

    # --------------------------------------------------------
    # S3 OBJECT KEY
    # --------------------------------------------------------

    object_key = (
        f"items/"
        f"branch_{item.branch_id}/"
        f"item_{item.id}/"
        f"{filename}"
    )

    # --------------------------------------------------------
    # UPLOAD TO S3
    # --------------------------------------------------------

    image_url = await upload_file_to_s3(
        file=image,
        object_key=object_key,
    )

    # --------------------------------------------------------
    # SAVE URL TO DATABASE WITH ROLLBACK SAFETY
    # --------------------------------------------------------

    try:
        item.image = image_url
        await db.commit()
        await db.refresh(item)
    except Exception as exc:
        await db.rollback()
        try:
            await delete_file_from_s3(object_key)
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Database update failed after S3 upload: {exc}",
        ) from exc

    # --------------------------------------------------------
    # CACHE INVALIDATION
    # --------------------------------------------------------

    await Cache.clear_menu_cache(item.branch_id, item.client_id)

    return {
        "message": "Image uploaded successfully",
        "image_url": image_url,
    }


# ============================================================
# UPDATE ITEM IMAGE
# ============================================================

async def update_image_service(
    item_id: int,
    image: UploadFile,
    db,
):

    # --------------------------------------------------------
    # FIND ITEM
    # --------------------------------------------------------

    item = await db.get(
        Item,
        item_id,
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    # --------------------------------------------------------
    # FILE EXTENSION
    # --------------------------------------------------------

    extension = Path(
        image.filename or ""
    ).suffix.lower()

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    if extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, JPEG, PNG and WEBP "
                "images are allowed"
            ),
        )

    # --------------------------------------------------------
    # CREATE NEW FILE NAME
    # --------------------------------------------------------

    filename = (
        f"{uuid4()}"
        f"{extension}"
    )

    # --------------------------------------------------------
    # NEW S3 KEY
    # --------------------------------------------------------

    object_key = (
        f"items/"
        f"branch_{item.branch_id}/"
        f"item_{item.id}/"
        f"{filename}"
    )

    # --------------------------------------------------------
    # KEEP OLD IMAGE KEY (S3 ONLY, RETURNS NONE FOR LOCAL /uploads/...)
    # --------------------------------------------------------

    old_object_key = None

    if item.image:

        old_object_key = get_s3_object_key(
            item.image
        )

    # --------------------------------------------------------
    # UPLOAD NEW IMAGE FIRST
    # --------------------------------------------------------

    new_image_url = await upload_file_to_s3(
        file=image,
        object_key=object_key,
    )

    # --------------------------------------------------------
    # UPDATE DATABASE WITH ROLLBACK SAFETY
    # --------------------------------------------------------

    try:
        item.image = new_image_url
        await db.commit()
        await db.refresh(item)
    except Exception as exc:
        await db.rollback()
        try:
            await delete_file_from_s3(object_key)
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Database update failed: {exc}",
        ) from exc

    # --------------------------------------------------------
    # DELETE OLD S3 OBJECT (ONLY AFTER DB COMMIT SUCCEEDS)
    # --------------------------------------------------------

    if old_object_key:

        try:
            await delete_file_from_s3(
                old_object_key
            )
        except Exception as delete_err:
            print(f"[update_image_service] Warning: Failed to delete old S3 object '{old_object_key}': {delete_err}")

    # --------------------------------------------------------
    # CACHE INVALIDATION
    # --------------------------------------------------------

    await Cache.clear_menu_cache(item.branch_id, item.client_id)

    return {
        "message": "Image updated successfully",
        "image_url": new_image_url,
    }

