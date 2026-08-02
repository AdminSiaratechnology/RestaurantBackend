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
        final_branch_id = user.selected_branch_id

        if not final_branch_id:
            raise HTTPException(
                status_code=400,
                detail="Staff branch not assigned"
            )

    elif role == "client":
        if not branch_id:
            raise HTTPException(
                status_code=400,
                detail="branch_id is required"
            )

        final_branch_id = branch_id

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

    if cached_data:
        return cached_data

    # =====================================================
    # QUERY
    # =====================================================

    query = (
        select(Item)
        .outerjoin(
            Pricing,
            (Pricing.item_id == Item.id)
            & (Pricing.branch_id == final_branch_id)
            & (Pricing.is_active == True)
        )
        .options(
            selectinload(Item.pricings)
        )
        .where(
            Item.branch_id == final_branch_id
        )
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

    await Cache.set(
        cache_key,
        jsonable_encoder(items),
        expire=600
    )

    return items


async def create_item_service(
    payload,
    db,
    current
):
    client = await get_client_if_accessible(
        client_id=payload.client_id,
        db=db,
        current=current
    )

    result = await db.execute(
        select(Category).where(
            Category.id == payload.category_id,
            Category.client_id == client.id
        )
    )

    category = result.scalar_one_or_none()

    if not category or category.branch_id != payload.branch_id:
        raise HTTPException(400, "Invalid category for this branch")

    result = await db.execute(
        select(Branch).where(
            Branch.id == payload.branch_id,
            Branch.client_id == client.id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(400, "Invalid branch")

    result = await db.execute(
        select(Item).where(
            Item.name == payload.name,
            Item.branch_id == payload.branch_id,
            Item.client_id == client.id
        )
    )

    if result.scalar_one_or_none():
        raise HTTPException(
            400,
            "Item already exists in this branch"
        )

    item = Item(
        name=payload.name,
        client_id=client.id,
        category_id=payload.category_id,
        branch_id=payload.branch_id,
        food_type=payload.food_type
    )

    db.add(item)

    await db.commit()

    result = await db.execute(
        select(Item)
        .options(selectinload(Item.pricings))
        .where(Item.id == item.id)
    )

    await Cache.delete_pattern(f"products:branch:{payload.branch_id}:*")
    await Cache.delete(f"menu:branch:{payload.branch_id}")

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

        # if result.scalar_one_or_none():
        #     raise HTTPException(400, "Duplicate name")

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

    await Cache.delete_pattern(f"products:branch:{item.branch_id}:*")
    await Cache.delete(f"menu:branch:{item.branch_id}")

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

    await db.delete(item)
    await db.commit()

    await Cache.delete_pattern(f"products:branch:{branch_id}:*")
    await Cache.delete(f"menu:branch:{branch_id}")

    return {"message": "Item deleted"}


async def upload_image_service(
    item_id,
    image: UploadFile,
    db
):
    item = await db.get(Item, item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    ext = Path(image.filename).suffix.lower()
    filename = f"{uuid4()}{ext}"

    upload_dir = (
        Path("uploads")
        / "items"
        / f"branch_{item.branch_id}"
        / f"item_{item.id}"
    )

    upload_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = upload_dir / filename

    with open(file_path, "wb") as buffer:
        buffer.write(await image.read())

    image_url = (
        f"/uploads/items/"
        f"branch_{item.branch_id}/"
        f"item_{item.id}/"
        f"{filename}"
    )

    item.image = image_url

    await db.commit()

    await Cache.delete_pattern(f"products:branch:{item.branch_id}:*")
    await Cache.delete(f"menu:branch:{item.branch_id}")

    return {
        "image_url": image_url
    }


async def update_image_service(
    item_id,
    image: UploadFile,
    db
):
    item = await db.get(Item, item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    if item.image:
        old_path = Path(item.image.lstrip("/"))

        if old_path.exists():
            old_path.unlink()

    ext = Path(image.filename).suffix.lower()
    filename = f"{uuid4()}{ext}"

    upload_dir = (
        Path("uploads")
        / "items"
        / f"branch_{item.branch_id}"
        / f"item_{item.id}"
    )

    upload_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = upload_dir / filename

    with open(file_path, "wb") as buffer:
        buffer.write(await image.read())

    image_url = (
        f"/uploads/items/"
        f"branch_{item.branch_id}/"
        f"item_{item.id}/"
        f"{filename}"
    )

    item.image = image_url

    await db.commit()
    await db.refresh(item)

    await Cache.delete_pattern(f"products:branch:{item.branch_id}:*")
    await Cache.delete(f"menu:branch:{item.branch_id}")

    return {
        "message": "Image updated successfully",
        "image_url": image_url
    }