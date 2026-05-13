from unittest import result
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app import db
from app.accounts.branch.model import Branch
from app.accounts.client.model import Client
from app.accounts.deps import get_current_user, get_client_if_accessible
from app.accounts.item.model import Item
from app.accounts.item.schema import ItemCreate, ItemUpdate, ItemOut
from app.accounts.category.model import Category
from app.accounts.pricing.model import Pricing
from app.db.config import SessionDep
from app.accounts.deps import access_four, UserRole

router = APIRouter(prefix="/items", tags=["Items"])


# ✅ CREATE ITEM
@router.post("/", response_model=ItemOut)
async def create_item(
    payload: ItemCreate,
    db: SessionDep,
    current=Depends(access_four)
):

    # 🔐 Tenant Access
    client = await get_client_if_accessible(
        client_id=payload.client_id,
        db=db,
        current=current
    )

    # ✅ Validate Category
    result = await db.execute(
        select(Category).where(
            Category.id == payload.category_id,
            Category.client_id == client.id
        )
    )

    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(400, "Invalid category")

    # ✅ Validate Branch
    result = await db.execute(
        select(Branch).where(
            Branch.id == payload.branch_id,
            Branch.client_id == client.id
        )
    )

    branch = result.scalar_one_or_none()

    if not branch:
        raise HTTPException(400, "Invalid branch")

    # ✅ Duplicate Check
    result = await db.execute(
        select(Item).where(
            Item.name == payload.name,
            Item.branch_id == payload.branch_id
        )
    )

    if result.scalar_one_or_none():
        raise HTTPException(
            400,
            "Item already exists in this branch"
        )

    # ✅ Create Item
    item = Item(
        name=payload.name,
        client_id=client.id,
        category_id=payload.category_id,
        branch_id=payload.branch_id
    )

    db.add(item)

    # ✅ flush generates item.id BEFORE commit
    await db.flush()

    # ✅ Create Pricing Automatically
    pricing = Pricing(
        client_id=client.id,
        item_id=item.id,
        branch_id=payload.branch_id,
        price=payload.price,
        is_active=True
    )

    db.add(pricing)

    # ✅ commit both together
    await db.commit()

    # ✅ reload with relationship
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.pricings))
        .where(Item.id == item.id)
    )

    created_item = result.scalar_one()

    return created_item


# ✅ GET ITEMS
@router.get("/get_items", response_model=list[ItemOut])
async def get_items(
    db: SessionDep,
    current=Depends(access_four)
):
    role = current["role"]
    user = current["user"]

    query = select(Item).options(
        selectinload(Item.pricings)   # ✅ auto fetch pricing
    )

    if role == "super_admin":
        pass

    elif role == "partner":
        query = query.join(Item.client).where(
            Client.partner_id == user.id
        )

    elif role == "client":
        query = query.where(
            Item.client_id == user.id
        )

    elif role == "staff":
        query = query.where(
            Item.client_id == user.client_id
        )

    else:
        raise HTTPException(403, "Not authorized")

    result = await db.execute(query)

    return result.scalars().unique().all()




# @router.get("/{item_id}", response_model=ItemOut)
# async def get_item(
#     item_id: int,
#     db: SessionDep,
#     current=Depends(get_current_user)
# ):
#     role = current["role"]
#     user = current["user"]

#     # 🔍 Get item
#     item = await db.get(Item, item_id)
#     if not item:
#         raise HTTPException(404, "Item not found")

#     # 🔐 Tenant Access Check
#     await get_tenant_if_accessible(
#         db, item.client_id, role, user
#     )

#     return item


# ✅ UPDATE ITEM
@router.put("/{item_id}", response_model=ItemOut)
async def update_item(
    item_id: int,
    payload: ItemUpdate,
    db: SessionDep,
    current=Depends(access_four)
):

    item = await db.get(Item, item_id)

    if not item:
        raise HTTPException(404, "Item not found")

    await get_client_if_accessible(
        client_id=item.client_id,
        db=db,
        current=current
    )

    # ✅ validate category
    if payload.category_id:
        result = await db.execute(
            select(Category).where(
                Category.id == payload.category_id,
                Category.client_id == item.client_id
            )
        )

        if not result.scalar_one_or_none():
            raise HTTPException(400, "Invalid category")

    # ✅ duplicate name check
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

    # ✅ update item fields
    item_data = payload.dict(
        exclude_unset=True,
        exclude={"price", "pricing_is_active"}
    )

    for key, value in item_data.items():
        setattr(item, key, value)

    # ✅ pricing update
    if payload.price is not None or payload.pricing_is_active is not None:

        result = await db.execute(
            select(Pricing).where(
                Pricing.item_id == item.id
            )
        )

        pricing = result.scalar_one_or_none()

        # ✅ create pricing if missing
        if not pricing:
            pricing = Pricing(
                item_id=item.id,
                client_id=item.client_id,
                branch_id=item.branch_id,
                price=payload.price or 0
            )

            db.add(pricing)

        else:
            if payload.price is not None:
                pricing.price = payload.price

            if payload.pricing_is_active is not None:
                pricing.is_active = payload.pricing_is_active

    await db.commit()

    # ✅ reload with relationships
    result = await db.execute(
        select(Item)
        .options(selectinload(Item.pricings))
        .where(Item.id == item.id)
    )

    updated_item = result.scalar_one()

    return updated_item


# ✅ DELETE ITEM
@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    db: SessionDep,
    current=Depends(access_four)
):
    role = current["role"]
    user = current["user"]

    item = await db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    # 🔐 ACCESS CHECK
    client = await get_client_if_accessible(
        client_id=item.client_id,
        db=db,
        current=current
    )

    await db.delete(item)
    await db.commit()

    return {"message": "Item deleted"}

