from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.accounts.branch.model import Branch
from app.accounts.category.model import Category
from app.accounts.deps import get_client_if_accessible
from app.accounts.item.model import Item
from app.accounts.pricing.model import Pricing


async def get_items_service(
    db,
    current,
    branch_id=None,
    limit=None,
    cursor=None,
    search=None,
    category_id=None,
):
    role = current["role"]
    user = current["user"]

    if role == "staff":
        final_branch_id = user.selected_branch_id

        if not final_branch_id:
            raise HTTPException(400, "Staff branch not assigned")

    elif role == "client":
        if not branch_id:
            raise HTTPException(400, "branch_id is required")

        final_branch_id = branch_id

    else:
        raise HTTPException(403, "Access denied")

    result = await db.execute(
        select(Branch).where(
            Branch.id == final_branch_id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(404, "Branch not found")

    query = (
        select(Item)
        .options(selectinload(Item.pricings))
        .where(Item.branch_id == final_branch_id)
    )

    if category_id:
        query = query.where(
            Item.category_id == category_id
        )

    if search:
        query = query.where(
            Item.name.ilike(f"%{search}%")
        )

    if cursor:
        query = query.where(
            Item.id > cursor
        )

    query = query.order_by(Item.id.asc())

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)

    return result.scalars().all()


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

    if not category:
        raise HTTPException(400, "Invalid category")

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
        branch_id=payload.branch_id
    )

    db.add(item)

    await db.commit()

    result = await db.execute(
        select(Item)
        .options(selectinload(Item.pricings))
        .where(Item.id == item.id)
    )

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

        if not result.scalar_one_or_none():
            raise HTTPException(400, "Invalid category")

    if payload.name:
        result = await db.execute(
            select(Item).where(
                Item.name == payload.name,
                Item.client_id == item.client_id,
                Item.id != item_id
            )
        )

        if result.scalar_one_or_none():
            raise HTTPException(400, "Duplicate name")

    item_data = payload.dict(
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
                is_active=payload.pricing_is_active or True
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

    await db.delete(item)
    await db.commit()

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

    return {
        "message": "Image updated successfully",
        "image_url": image_url
    }