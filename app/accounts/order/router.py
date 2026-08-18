from typing import Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from app.accounts.crm.loyalty.service import (
    update_customer_after_order,
    calculate_customer_rank,
    recalculate_customer_crm,
)

from app.accounts.client.model import Client
from app.accounts.customer.model import Customer
from app.accounts.crm.customer_history.model import CustomerVisitHistory
from app.accounts.crm.rank_rules.model import CRMBranchRankRule
from app.accounts.deps import access_one, get_client_if_accessible
from app.accounts.enum import UserRole
from app.accounts.inventory.service import consume_inventory_for_item
from app.accounts.inventory.service import consume_inventory_for_item
from app.accounts.item.model import Item
from app.accounts.order.enum import OrderType
from app.accounts.order.model import Order, OrderItem
from app.accounts.order.schema import (
    CursorPaginatedResponse,
    OrderCreate,
    OrderItemStatusResponse,
    OrderItemStatusUpdate,
    OrderResponse,
    OrderUpdate,
)
from app.accounts.order.service import (
    get_menu_all_branches,
    get_orders_all_branches,
)
from app.accounts.pricing.model import Pricing
from app.accounts.table.model import Table, TableStatus
from app.core.cache import Cache
from app.db.config import SessionDep

router = APIRouter(
    prefix="/order",
    tags=["Order"],
)


# ============================================================
# HELPERS
# ============================================================


def compute_total_price(pricing: Pricing) -> float:
    """
    Calculate final unit price.

    Formula:

        discounted = price - discount
        total = discounted + tax
    """

    base = float(pricing.price or 0.0)
    discount = float(pricing.discount or 0.0)
    tax = float(pricing.tax or 0.0)

    discounted = base - (
        base * discount / 100.0
    )

    total = discounted + (
        discounted * tax / 100.0
    )

    return round(total, 2)


def order_item_line_snapshot(
    pricing: Pricing,
    quantity: int,
) -> dict[str, float]:

    unit_price = float(
        pricing.price or 0.0
    )

    discount_percent = float(
        pricing.discount or 0.0
    )

    tax_percent = float(
        pricing.tax or 0.0
    )

    discounted_unit = (
        unit_price
        - (
            unit_price
            * discount_percent
            / 100.0
        )
    )

    tax_per_unit = (
        discounted_unit
        * tax_percent
        / 100.0
    )

    final_unit = (
        discounted_unit
        + tax_per_unit
    )

    return {
        "unit_price": round(
            unit_price,
            2,
        ),
        "discount_percent": round(
            discount_percent,
            2,
        ),
        "tax_percent": round(
            tax_percent,
            2,
        ),
        "subtotal": round(
            discounted_unit * quantity,
            2,
        ),
        "tax_amount": round(
            tax_per_unit * quantity,
            2,
        ),
        "total_price": round(
            final_unit * quantity,
            2,
        ),
        "line_unit_final": round(
            final_unit,
            2,
        ),
    }


def build_order_item(
    order_id: int,
    item_id: int,
    quantity: int,
    pricing: Pricing,
) -> OrderItem:

    snap = order_item_line_snapshot(
        pricing,
        quantity,
    )

    return OrderItem(
        order_id=order_id,
        item_id=item_id,
        quantity=quantity,

        unit_price=snap["unit_price"],

        discount_percent=(
            snap["discount_percent"]
        ),

        tax_percent=(
            snap["tax_percent"]
        ),

        subtotal=snap["subtotal"],

        tax_amount=snap["tax_amount"],

        total_price=snap["total_price"],
    )


# ============================================================
# PRICING RESOLUTION
# ============================================================


async def resolve_pricing(
    db: SessionDep,
    db_item: Item,
    client_id: int,
    branch_id: int,
) -> Pricing:

    # --------------------------------------------------------
    # 1. Exact active branch pricing
    # --------------------------------------------------------

    result = await db.execute(
        select(Pricing)
        .where(
            Pricing.item_id == db_item.id,
            Pricing.client_id == client_id,
            Pricing.branch_id == branch_id,
            Pricing.is_active.is_(True),
        )
        .order_by(Pricing.id.desc())
    )

    pricing = result.scalars().first()

    if pricing:
        return pricing

    # --------------------------------------------------------
    # 2. Any active pricing for this client/item
    # --------------------------------------------------------

    result = await db.execute(
        select(Pricing)
        .where(
            Pricing.item_id == db_item.id,
            Pricing.client_id == client_id,
            Pricing.is_active.is_(True),
        )
        .order_by(Pricing.id.desc())
    )

    pricing = result.scalars().first()

    if pricing:

        # Already belongs to branch
        if pricing.branch_id == branch_id:
            return pricing

        # Clone pricing for this branch
        cloned = Pricing(
            client_id=client_id,
            branch_id=branch_id,
            item_id=db_item.id,

            price=pricing.price,
            cost_price=pricing.cost_price,
            discount=pricing.discount,
            tax=pricing.tax,
            calories=pricing.calories,

            is_active=True,
        )

        db.add(cloned)

        await db.flush()

        return cloned

    # --------------------------------------------------------
    # 3. Template / inactive pricing fallback
    # --------------------------------------------------------

    result = await db.execute(
        select(Pricing)
        .where(
            Pricing.item_id == db_item.id,
            Pricing.client_id == client_id,
        )
        .order_by(Pricing.id.desc())
    )

    template = result.scalars().first()

    if template:

        created = Pricing(
            client_id=client_id,
            branch_id=branch_id,
            item_id=db_item.id,

            price=template.price,
            cost_price=template.cost_price,
            discount=template.discount,
            tax=template.tax,
            calories=template.calories,

            is_active=True,
        )

        db.add(created)

        await db.flush()

        return created

    raise HTTPException(
        status_code=400,
        detail=(
            f"No pricing for '{db_item.name}'. "
            "Add pricing before placing an order."
        ),
    )


# ============================================================
# CUSTOMER VISIT HISTORY
# ============================================================


# ============================================================
# CUSTOMER VISIT HISTORY
# ============================================================


async def create_customer_visit_history(
    db,
    customer: Customer,
    order: Order,
) -> CustomerVisitHistory:

    result = await db.execute(
        select(CustomerVisitHistory)
        .where(
            CustomerVisitHistory.order_id
            == order.id
        )
    )

    history = result.scalar_one_or_none()

    visit_type_val = (
        order.order_type.value
        if hasattr(
            order.order_type,
            "value",
        )
        else (
            str(order.order_type)
            if order.order_type
            else None
        )
    )

    if history:

        history.customer_id = customer.id
        history.client_id = order.client_id
        history.branch_id = order.branch_id
        history.visit_date = (
            order.created_at
            or datetime.utcnow()
        )
        history.total_amount = float(
            order.total_amount or 0.0
        )
        history.visit_type = visit_type_val

    else:

        history = CustomerVisitHistory(
            customer_id=customer.id,
            order_id=order.id,
            bill_id=None,

            client_id=order.client_id,
            branch_id=order.branch_id,

            visit_date=(
                order.created_at
                or datetime.utcnow()
            ),

            total_amount=float(
                order.total_amount or 0.0
            ),

            discount=0.0,
            tax=0.0,

            payment_method=None,
            table_name=None,

            visit_type=visit_type_val,
        )

        db.add(history)

    await db.flush()

    return history


# ============================================================
# CUSTOMER LOOKUP / CREATE
# ============================================================


async def resolve_order_customer(
    db,
    data: OrderCreate,
) -> Customer | None:

    name = (
        data.customer_name.strip()
        if data.customer_name
        else ""
    )

    phone = (
        data.customer_phone.strip()
        if data.customer_phone
        else None
    )

    email = (
        data.customer_email.strip().lower()
        if getattr(data, "customer_email", None)
        else None
    )

    # --------------------------------------------------------
    # GUEST
    #
    # Customer requires:
    #
    # name + phone
    # OR
    # name + email
    #
    # Otherwise DO NOT create customer.
    # --------------------------------------------------------

    if not name:
        return None

    if not phone and not email:
        return None

    # --------------------------------------------------------
    # Find existing customer
    # --------------------------------------------------------

    conditions = []

    if phone:
        conditions.append(
            Customer.phone == phone
        )

    if email:
        conditions.append(
            func.lower(Customer.email)
            == email
        )

    result = await db.execute(
        select(Customer)
        .where(
            Customer.client_id
            == data.client_id,

            or_(*conditions),
        )
        .order_by(
            Customer.id.desc()
        )
    )

    customer = result.scalars().first()

    if customer:

        # Update missing information
        if name and not customer.name:
            customer.name = name

        if phone and not customer.phone:
            customer.phone = phone

        if email and not customer.email:
            customer.email = email

        if customer.branch_id is None:
            customer.branch_id = data.branch_id

        await db.flush()

        print(
            "[CRM] Existing customer found: "
            f"{customer.id}"
        )

        return customer

    # --------------------------------------------------------
    # Create new customer
    # --------------------------------------------------------

    customer = Customer(
        name=name,

        phone=phone,

        email=email,

        client_id=data.client_id,

        branch_id=data.branch_id,

        total_spend=0.0,

        total_orders=0,

        total_visits=0,

        average_order_value=0.0,

        last_order_amount=0.0,

        current_rank="bronze",

        loyalty_points=0.0,
    )

    db.add(customer)

    await db.flush()

    print(
        "[CRM] New customer created: "
        f"{customer.id}"
    )

    return customer


# ============================================================
# GET MENU
# ============================================================


@router.get("/menu")
async def get_menu(
    db: SessionDep,
    client_id: int | None = None,
    branch_id: int | None = None,
    current=Depends(access_one),
):

    try:

        role = current["role"]
        user = current["user"]

        # ----------------------------------------------------
        # STAFF SECURITY
        # ----------------------------------------------------

        if role == UserRole.STAFF:

            client_id = user.client_id
            branch_id = user.branch_id

        else:

            if (
                client_id is None
                or branch_id is None
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "client_id and branch_id "
                        "are required parameters"
                    ),
                )

        await get_client_if_accessible(
            client_id,
            db,
            current,
        )

        cache_key = (
            f"menu:client:{client_id}:"
            f"branch:{branch_id}"
        )

        cached_menu = await Cache.get(
            cache_key
        )

        if cached_menu:
            return cached_menu

        result = await db.execute(
            select(Item)
            .options(
                selectinload(Item.category),
                selectinload(Item.pricings),
            )
            .where(
                Item.client_id == client_id,
                Item.branch_id == branch_id,
                Item.is_active.is_(True),
            )
        )

        items = result.scalars().all()

        menu: dict[str, list] = {}

        for item in items:

            category_name = (
                item.category.name
                if (
                    item.category
                    and item.category.branch_id
                    == branch_id
                )
                else "Others"
            )

            pricing = next(
                (
                    p
                    for p in item.pricings
                    if (
                        p.branch_id
                        == branch_id
                        and p.is_active
                    )
                ),
                None,
            )

            if pricing:

                base_price = float(
                    pricing.price or 0.0
                )

                total_price = (
                    compute_total_price(
                        pricing
                    )
                )

                discount = float(
                    pricing.discount or 0.0
                )

                tax = float(
                    pricing.tax or 0.0
                )

            else:

                base_price = 0.0
                total_price = 0.0
                discount = 0.0
                tax = 0.0

            menu.setdefault(
                category_name,
                [],
            ).append(
                {
                    "id": item.id,
                    "name": item.name,
                    "price": base_price,
                    "discount": discount,
                    "tax": tax,
                    "total_price": total_price,
                }
            )

        await Cache.set(
            cache_key,
            menu,
            expire=600,
        )

        return menu

    except HTTPException:
        raise

    except SQLAlchemyError as e:

        print(
            "GET MENU ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Database error while "
                "fetching menu"
            ),
        )


# ============================================================
# GET ALL ORDERS
# ============================================================


@router.get(
    "/get_all_orders",
    response_model=list[OrderResponse],
)
async def get_all_orders(
    db: SessionDep,
    branch_id: int | None = None,
    current=Depends(access_one),
):

    try:

        role = current["role"]
        user = current["user"]

        query = (
            select(Order)
            .options(
                selectinload(
                    Order.order_items
                ).selectinload(
                    OrderItem.item
                )
            )
        )

        if branch_id:
            query = query.where(
                Order.branch_id
                == branch_id
            )

        if role.name == "CLIENT":

            query = query.where(
                Order.client_id
                == user.id
            )

        elif role.name == "PARTNER":

            query = (
                query
                .join(
                    Client,
                    Client.id
                    == Order.client_id,
                )
                .where(
                    Client.partner_id
                    == user.id
                )
            )

        result = await db.execute(
            query.order_by(
                Order.id.desc()
            )
        )

        orders = result.scalars().all()

        # ----------------------------------------------------
        # Load tables once
        # ----------------------------------------------------

        table_query = select(Table)

        if branch_id:

            table_query = table_query.where(
                Table.branch_id
                == branch_id
            )

        table_result = await db.execute(
            table_query
        )

        tables = {
            table.id: table
            for table in
            table_result.scalars().all()
        }

        final_orders = []

        for order in orders:

            table_name = None

            if order.table_id:

                table = tables.get(
                    order.table_id
                )

                if table:

                    table_name = (
                        f"{table.name}"
                        if not table.floor
                        else (
                            f"{table.name} "
                            f"({table.floor})"
                        )
                    )

            final_orders.append(
                {
                    "id": order.id,

                    "client_id":
                        order.client_id,

                    "branch_id":
                        order.branch_id,

                    "table_id":
                        order.table_id,

                    "table_name":
                        table_name,

                    "order_type":
                        order.order_type,

                    "customer_name":
                        order.customer_name,

                    "customer_phone":
                        order.customer_phone,

                    "notes":
                        order.notes,

                    "status":
                        order.status,

                    "total_amount":
                        order.total_amount,

                    "created_at":
                        order.created_at,

                    "items": [
                        {
                            "id": item.id,

                            "item_id":
                                item.item_id,

                            "item_name": (
                                item.item.name
                                if item.item
                                else None
                            ),

                            "quantity":
                                item.quantity,

                            "price":
                                getattr(
                                    item,
                                    "price",
                                    None,
                                ),

                            "order_status":
                                item.order_status,
                        }
                        for item
                        in order.order_items
                    ],
                }
            )

        return final_orders

    except SQLAlchemyError as e:

        print(
            "GET ORDERS ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Database error while "
                "fetching orders"
            ),
        )


# ============================================================
# GET PAGINATED ORDERS
# ============================================================


@router.get(
    "/orders_paginated",
    response_model=CursorPaginatedResponse[OrderResponse],
)
async def get_orders_paginated(
    db: SessionDep,
    client_id: int | None = None,
    branch_id: int | None = None,
    cursor: int | None = None,
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),
    status: str | None = None,
    search: str | None = None,
    current=Depends(access_one),
):
    try:
        role = current["role"]
        user = current["user"]

        # ====================================================
        # ORDER QUERY
        # ====================================================

        query = select(Order)

        # ----------------------------------------------------
        # Filters
        # ----------------------------------------------------

        if client_id is not None:
            query = query.where(
                Order.client_id == client_id
            )

        if branch_id is not None:
            query = query.where(
                Order.branch_id == branch_id
            )

        # ----------------------------------------------------
        # CLIENT ACCESS
        # ----------------------------------------------------

        if role.name == "CLIENT":

            query = query.where(
                Order.client_id == user.id
            )

        # ----------------------------------------------------
        # PARTNER ACCESS
        # ----------------------------------------------------

        elif role.name == "PARTNER":

            query = (
                query
                .join(
                    Client,
                    Client.id == Order.client_id,
                )
                .where(
                    Client.partner_id == user.id
                )
            )

        # ----------------------------------------------------
        # STATUS FILTER
        # ----------------------------------------------------

        if status:
            query = query.where(
                Order.status == status
            )

        # ----------------------------------------------------
        # SEARCH
        # ----------------------------------------------------

        if search:

            search_term = (
                f"%{search.strip()}%"
            )

            query = query.where(
                or_(
                    Order.customer_name.ilike(
                        search_term
                    ),
                    Order.customer_phone.ilike(
                        search_term
                    ),
                    Order.notes.ilike(
                        search_term
                    ),
                )
            )

        # ----------------------------------------------------
        # CURSOR
        # ----------------------------------------------------

        if cursor is not None:

            query = query.where(
                Order.id < cursor
            )

        # ----------------------------------------------------
        # ORDER BY
        # ----------------------------------------------------

        query = query.order_by(
            Order.id.desc()
        )

        # ====================================================
        # COUNT QUERY
        # ====================================================

        count_query = select(
            func.count(Order.id)
        )

        if client_id is not None:

            count_query = count_query.where(
                Order.client_id == client_id
            )

        if branch_id is not None:

            count_query = count_query.where(
                Order.branch_id == branch_id
            )

        # ----------------------------------------------------
        # CLIENT COUNT ACCESS
        # ----------------------------------------------------

        if role.name == "CLIENT":

            count_query = count_query.where(
                Order.client_id == user.id
            )

        # ----------------------------------------------------
        # PARTNER COUNT ACCESS
        # ----------------------------------------------------

        elif role.name == "PARTNER":

            count_query = (
                count_query
                .join(
                    Client,
                    Client.id == Order.client_id,
                )
                .where(
                    Client.partner_id == user.id
                )
            )

        # ----------------------------------------------------
        # STATUS COUNT
        # ----------------------------------------------------

        if status:

            count_query = count_query.where(
                Order.status == status
            )

        # ----------------------------------------------------
        # SEARCH COUNT
        # ----------------------------------------------------

        if search:

            search_term = (
                f"%{search.strip()}%"
            )

            count_query = count_query.where(
                or_(
                    Order.customer_name.ilike(
                        search_term
                    ),
                    Order.customer_phone.ilike(
                        search_term
                    ),
                    Order.notes.ilike(
                        search_term
                    ),
                )
            )

        count_result = await db.execute(
            count_query
        )

        total_count = count_result.scalar_one()

        # ====================================================
        # FETCH ORDERS
        # ====================================================

        query = query.limit(
            limit + 1
        )

        # IMPORTANT:
        # Load OrderItem + Item
        query = query.options(
            selectinload(
                Order.order_items
            ).selectinload(
                OrderItem.item
            )
        )

        result = await db.execute(
            query
        )

        orders = result.scalars().all()

        # ====================================================
        # PAGINATION
        # ====================================================

        has_more = len(orders) > limit

        items = orders[:limit]

        next_cursor = None

        if has_more and items:

            next_cursor = items[-1].id

        # ====================================================
        # LOAD TABLES
        #
        # Table model:
        #
        # class Table:
        #     id
        #     name
        #     floor
        #
        # So we MUST use table.name
        # ====================================================

        tables_query = select(Table)

        # ----------------------------------------------------
        # If branch filter is provided, only load that branch
        # ----------------------------------------------------

        if branch_id is not None:

            tables_query = tables_query.where(
                Table.branch_id == branch_id
            )

        # ----------------------------------------------------
        # IMPORTANT:
        # If branch_id is NOT provided, load tables for all
        # order branches.
        # ----------------------------------------------------

        else:

            order_branch_ids = list(
                {
                    order.branch_id
                    for order in items
                    if order.branch_id is not None
                }
            )

            if order_branch_ids:

                tables_query = tables_query.where(
                    Table.branch_id.in_(
                        order_branch_ids
                    )
                )

        tables_result = await db.execute(
            tables_query
        )

        table_list = (
            tables_result.scalars().all()
        )

        # ----------------------------------------------------
        # Create table_id -> Table mapping
        # ----------------------------------------------------

        tables = {
            table.id: table
            for table in table_list
        }

        # ====================================================
        # BUILD RESPONSE
        # ====================================================

        final_orders = []

        for order in items:

            # ------------------------------------------------
            # TABLE NAME
            # ------------------------------------------------

            table_name = None

            if order.table_id is not None:

                table = tables.get(
                    order.table_id
                )

                if table:

                    # Your Table model has:
                    #
                    # name = Column(String)
                    #
                    # So use table.name
                    table_name = table.name

                    # Optional floor
                    if table.floor:

                        table_name = (
                            f"{table.name} "
                            f"({table.floor})"
                        )

            # ------------------------------------------------
            # ORDER ITEMS
            # ------------------------------------------------

            enriched_items = []

            for order_item in order.order_items:

                item_name = None

                if order_item.item:

                    item_name = (
                        order_item.item.name
                    )

                enriched_items.append(
                    {
                        "id": order_item.id,

                        "item_id":
                            order_item.item_id,

                        "item_name":
                            item_name,

                        "quantity":
                            order_item.quantity,

                        "price":
                            getattr(
                                order_item,
                                "price",
                                None,
                            ),

                        "order_status":
                            order_item.order_status,
                    }
                )

            # ------------------------------------------------
            # ORDER RESPONSE
            # ------------------------------------------------

            final_orders.append(
                {
                    "id":
                        order.id,

                    "client_id":
                        order.client_id,

                    "branch_id":
                        order.branch_id,

                    "table_id":
                        order.table_id,

                    # IMPORTANT:
                    # Schema expects table_name
                    # NOT table_number
                    "table_name":
                        table_name,

                    "order_type":
                        order.order_type,

                    "customer_name":
                        order.customer_name,

                    "customer_phone":
                        order.customer_phone,

                    "notes":
                        order.notes,

                    "status":
                        order.status,

                    "total_amount":
                        float(
                            order.total_amount or 0
                        ),

                    "created_at":
                        order.created_at,

                    "items":
                        enriched_items,
                }
            )

        # ====================================================
        # FINAL RESPONSE
        # ====================================================

        return {
            "items":
                final_orders,

            "next_cursor":
                next_cursor,

            "has_more":
                has_more,

            "total_count":
                total_count,

            "total_orders":
                total_count,
        }

    except HTTPException:
        raise

    except SQLAlchemyError as e:

        print(
            "PAGINATED ORDERS DB ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Database error while "
                "fetching orders"
            ),
        )

    except Exception as e:

        print(
            "PAGINATED ORDERS ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unexpected error: {str(e)}"
            ),
        )

# ============================================================
# CREATE ORDER
# ============================================================


@router.post("/create_order")
async def create_order(
    data: OrderCreate,
    db: SessionDep,
    current=Depends(access_one),
):
    try:

        role = current["role"]
        user = current["user"]

        # =================================================
        # STAFF SECURITY
        # =================================================

        if role == UserRole.STAFF:

            data.client_id = user.client_id
            data.branch_id = user.branch_id

        # =================================================
        # CLIENT ACCESS
        # =================================================

        await get_client_if_accessible(
            data.client_id,
            db,
            current,
        )

        # =================================================
        # RESOLVE CUSTOMER
        #
        # Customer is created only when:
        #
        # name + phone
        # OR
        # name + email
        #
        # Otherwise:
        #
        # customer = None
        # =================================================

        customer = await resolve_order_customer(
            db=db,
            data=data,
        )

        # =================================================
        # ORDER TYPE & TABLE VALIDATION
        # =================================================

        if data.order_type == OrderType.DINE_IN:

            if not data.table_id or data.table_id == 0:

                raise HTTPException(
                    status_code=400,
                    detail="Please select a table for dine-in orders.",
                )

            table = await db.get(
                Table,
                data.table_id,
            )

            if not table:

                raise HTTPException(
                    status_code=400,
                    detail="Selected table does not exist.",
                )

            if table.branch_id != data.branch_id:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Selected table does not "
                        "belong to this branch."
                    ),
                )

            if table.status == TableStatus.occupied:

                raise HTTPException(
                    status_code=400,
                    detail="Table is already occupied.",
                )

            table.status = TableStatus.occupied

            await Cache.delete(
                f"tables:branch:{table.branch_id}"
            )

        else:

            data.table_id = None

        # =================================================
        # CREATE ORDER
        # =================================================

        order = Order(
            client_id=data.client_id,
            branch_id=data.branch_id,
            table_id=data.table_id,
            order_type=data.order_type,

            customer_name=data.customer_name,
            customer_phone=data.customer_phone,

            customer_id=(
                customer.id
                if customer
                else None
            ),

            notes=data.notes,
        )

        db.add(order)

        await db.flush()

        # =================================================
        # ITEMS REQUIRED
        # =================================================

        if not data.items:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Order must contain "
                    "at least one item"
                ),
            )

        # =================================================
        # CREATE ORDER ITEMS
        # =================================================

        total = 0.0

        for item in data.items:

            if item.quantity <= 0:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid quantity "
                        f"for item {item.item_id}"
                    ),
                )

            # ---------------------------------------------
            # GET ITEM
            # ---------------------------------------------

            db_item = await db.get(
                Item,
                item.item_id,
            )

            if not db_item:

                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Item {item.item_id} "
                        "not found"
                    ),
                )

            # ---------------------------------------------
            # CLIENT SECURITY
            # ---------------------------------------------

            if db_item.client_id != data.client_id:

                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Item does not belong "
                        "to this client."
                    ),
                )

            # ---------------------------------------------
            # BRANCH SECURITY
            # ---------------------------------------------

            if (
                db_item.branch_id is not None
                and db_item.branch_id != data.branch_id
            ):

                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Item does not belong "
                        "to this branch."
                    ),
                )

            # ---------------------------------------------
            # PRICING
            # ---------------------------------------------

            pricing = await resolve_pricing(
                db=db,
                db_item=db_item,
                client_id=data.client_id,
                branch_id=data.branch_id,
            )

            # ---------------------------------------------
            # PRICE SNAPSHOT
            # ---------------------------------------------

            snap = order_item_line_snapshot(
                pricing,
                item.quantity,
            )

            total += snap["total_price"]

            # ---------------------------------------------
            # ORDER ITEM
            # ---------------------------------------------

            order_item = build_order_item(
                order_id=order.id,
                item_id=db_item.id,
                quantity=item.quantity,
                pricing=pricing,
            )

            db.add(order_item)

        # =================================================
        # ORDER TOTAL
        # =================================================

        order.total_amount = round(
            total,
            2,
        )

        await db.flush()

        # =================================================
        # CRM
        # =================================================

        new_rank = None
        history = None

        if customer:

            # ---------------------------------------------
            # UPDATE TOTAL SPEND
            # RANK
            # LOYALTY POINTS
            # ---------------------------------------------

            new_rank = await update_customer_after_order(
                db=db,
                customer=customer,
                order=order,
            )

            # ---------------------------------------------
            # CUSTOMER HISTORY
            # ---------------------------------------------

            history = await create_customer_visit_history(
                db=db,
                customer=customer,
                order=order,
            )

            # ---------------------------------------------
            # FORCE FLUSH
            # ---------------------------------------------

            await db.flush()

        # =================================================
        # FINAL COMMIT
        # =================================================

        await db.commit()

        # =================================================
        # REFRESH ORDER
        # =================================================

        await db.refresh(order)

        # =================================================
        # REFRESH CUSTOMER
        #
        # This guarantees the response gets the latest
        # loyalty_points/current_rank from DB.
        # =================================================

        if customer:

            await db.refresh(customer)

        # =================================================
        # CACHE
        # =================================================

        await Cache.delete(
            f"kitchen:branch:{order.branch_id}"
        )

        # =================================================
        # RESPONSE
        # =================================================

        return {
            "message": "Order created",

            "order_id": order.id,

            "customer_id": (
                customer.id
                if customer
                else None
            ),

            "is_guest": (
                customer is None
            ),

            "total": float(
                order.total_amount or 0.0
            ),

            "customer_total_spend": (
                float(
                    customer.total_spend or 0.0
                )
                if customer
                else None
            ),

            "customer_total_orders": (
                int(
                    customer.total_orders or 0
                )
                if customer
                else None
            ),

            "customer_total_visits": (
                int(
                    customer.total_visits or 0
                )
                if customer
                else None
            ),

            "customer_rank": (
                customer.current_rank
                if customer
                else None
            ),

            "loyalty_points": (
                float(
                    customer.loyalty_points or 0.0
                )
                if customer
                else None
            ),

            "history_id": (
                history.id
                if history
                else None
            ),
        }

    # =====================================================
    # HTTP ERROR
    # =====================================================

    except HTTPException:

        await db.rollback()
        raise

    # =====================================================
    # DATABASE ERROR
    # =====================================================

    except SQLAlchemyError as e:

        await db.rollback()

        print(
            "CREATE ORDER DB ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Database error: {str(e)}"
            ),
        )

    # =====================================================
    # UNKNOWN ERROR
    # =====================================================

    except Exception as e:

        await db.rollback()

        print(
            "CREATE ORDER UNEXPECTED ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Something went wrong: {str(e)}"
            ),
        )


# ============================================================
# UPDATE ORDER
# ============================================================


@router.put(
    "/orders_update/{order_id}",
    response_model=OrderResponse,
)
async def update_order(
    order_id: int,
    data: OrderUpdate,
    db: SessionDep,
    current=Depends(access_one),
):
    try:

        # ====================================================
        # GET ORDER
        # ====================================================

        result = await db.execute(
            select(Order)
            .where(Order.id == order_id)
        )

        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        # ====================================================
        # ACCESS
        # ====================================================

        await get_client_if_accessible(
            order.client_id,
            db,
            current,
        )

        if (
            current["role"] == UserRole.STAFF
            and order.branch_id != current["user"].branch_id
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Not allowed to update "
                    "orders of another branch"
                ),
            )

        # ====================================================
        # ONLY PENDING ORDERS CAN BE EDITED
        # ====================================================

        if str(order.status).lower() != "pending":
            raise HTTPException(
                status_code=400,
                detail="Only pending orders can be edited.",
            )

        # ====================================================
        # BASIC FIELDS
        # ====================================================

        if data.notes is not None:
            order.notes = data.notes

        old_order_type = order.order_type
        old_table_id = order.table_id

        if data.order_type is not None:
            order.order_type = data.order_type

        # ====================================================
        # TABLE HANDLING
        # ====================================================

        # If order type is DINE-IN
        if order.order_type == OrderType.DINE_IN:

            # ------------------------------------------------
            # Determine requested table
            # ------------------------------------------------

            requested_table_id = (
                data.table_id
                if data.table_id is not None
                else order.table_id
            )

            # ------------------------------------------------
            # Table is mandatory for dine-in
            # ------------------------------------------------

            if not requested_table_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Please select a table "
                        "for dine-in orders."
                    ),
                )

            # ------------------------------------------------
            # Get requested table
            # ------------------------------------------------

            new_table = await db.get(
                Table,
                requested_table_id,
            )

            if not new_table:
                raise HTTPException(
                    status_code=400,
                    detail="Selected table does not exist.",
                )

            # ------------------------------------------------
            # Branch validation
            # ------------------------------------------------

            if new_table.branch_id != order.branch_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Selected table does not "
                        "belong to this branch."
                    ),
                )

            # ------------------------------------------------
            # If changing table
            # ------------------------------------------------

            if (
                old_table_id != requested_table_id
            ):

                # --------------------------------------------
                # Check new table availability
                # --------------------------------------------

                if (
                    new_table.status
                    == TableStatus.occupied
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Selected table is "
                            "already occupied."
                        ),
                    )

                # --------------------------------------------
                # Release old table
                # --------------------------------------------

                if old_table_id:

                    old_table = await db.get(
                        Table,
                        old_table_id,
                    )

                    if old_table:

                        old_table.status = (
                            TableStatus.available
                        )

                        await Cache.delete(
                            f"tables:branch:"
                            f"{old_table.branch_id}"
                        )

                # --------------------------------------------
                # Occupy new table
                # --------------------------------------------

                new_table.status = (
                    TableStatus.occupied
                )

                await Cache.delete(
                    f"tables:branch:"
                    f"{new_table.branch_id}"
                )

                order.table_id = (
                    requested_table_id
                )

            else:

                # Same table
                # Make sure it remains occupied.

                if (
                    new_table.status
                    != TableStatus.occupied
                ):
                    new_table.status = (
                        TableStatus.occupied
                    )

                    await Cache.delete(
                        f"tables:branch:"
                        f"{new_table.branch_id}"
                    )

                order.table_id = (
                    requested_table_id
                )

        # ====================================================
        # NON DINE-IN
        # ====================================================

        else:

            # If changing from dine-in to takeaway/
            # delivery/etc., release previous table.

            if old_table_id:

                old_table = await db.get(
                    Table,
                    old_table_id,
                )

                if old_table:

                    old_table.status = (
                        TableStatus.available
                    )

                    await Cache.delete(
                        f"tables:branch:"
                        f"{old_table.branch_id}"
                    )

            order.table_id = None

        # ====================================================
        # UPDATE ITEMS
        # ====================================================

        if data.items is not None:

            # ------------------------------------------------
            # Delete existing items
            # ------------------------------------------------

            await db.execute(
                delete(OrderItem)
                .where(
                    OrderItem.order_id == order.id
                )
            )

            total = 0.0

            # ------------------------------------------------
            # Recreate items
            # ------------------------------------------------

            for item in data.items:

                if item.quantity <= 0:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Invalid quantity "
                            f"for item {item.item_id}"
                        ),
                    )

                # --------------------------------------------
                # GET ITEM
                # --------------------------------------------

                db_item = await db.get(
                    Item,
                    item.item_id,
                )

                if not db_item:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Item {item.item_id} "
                            "not found"
                        ),
                    )

                # --------------------------------------------
                # CLIENT VALIDATION
                # --------------------------------------------

                if (
                    db_item.client_id
                    != order.client_id
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            "Item does not belong "
                            "to this client."
                        ),
                    )

                # --------------------------------------------
                # BRANCH VALIDATION
                # --------------------------------------------

                if (
                    db_item.branch_id is not None
                    and db_item.branch_id
                    != order.branch_id
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            "Item does not belong "
                            "to this branch."
                        ),
                    )

                # --------------------------------------------
                # PRICING
                # --------------------------------------------

                pricing = await resolve_pricing(
                    db=db,
                    db_item=db_item,
                    client_id=order.client_id,
                    branch_id=order.branch_id,
                )

                # --------------------------------------------
                # PRICE SNAPSHOT
                # --------------------------------------------

                snap = order_item_line_snapshot(
                    pricing,
                    item.quantity,
                )

                total += snap["total_price"]

                # --------------------------------------------
                # CREATE ORDER ITEM
                # --------------------------------------------

                db.add(
                    build_order_item(
                        order_id=order.id,
                        item_id=db_item.id,
                        quantity=item.quantity,
                        pricing=pricing,
                    )
                )

            # ------------------------------------------------
            # UPDATE TOTAL
            # ------------------------------------------------

            order.total_amount = round(
                total,
                2,
            )

        # ====================================================
        # FLUSH
        # ====================================================

        await db.flush()

        # ====================================================
        # CRM
        # ====================================================

        customer = None

        if order.customer_id:

            customer = await db.get(
                Customer,
                order.customer_id,
            )

            if customer:

                await recalculate_customer_crm(
                    db=db,
                    customer_id=customer.id,
                    branch_id=order.branch_id,
                )

                # ------------------------------------------------
                # UPDATE CUSTOMER VISIT HISTORY
                # ------------------------------------------------

                history_result = await db.execute(
                    select(CustomerVisitHistory)
                    .where(
                        CustomerVisitHistory.order_id
                        == order.id
                    )
                )

                history = (
                    history_result.scalar_one_or_none()
                )

                if history:

                    history.total_amount = float(
                        order.total_amount or 0.0
                    )

                    history.branch_id = (
                        order.branch_id
                    )

                    history.visit_date = (
                        order.created_at
                        or datetime.utcnow()
                    )

                    history.visit_type = (
                        order.order_type.value
                        if hasattr(
                            order.order_type,
                            "value",
                        )
                        else str(
                            order.order_type
                        )
                    )

        # ====================================================
        # COMMIT
        # ====================================================

        await db.commit()

        # ====================================================
        # REFRESH
        # ====================================================

        await db.refresh(order)

        if customer:
            await db.refresh(customer)

        # ====================================================
        # CACHE
        # ====================================================

        await Cache.delete(
            f"kitchen:branch:{order.branch_id}"
        )

        # ====================================================
        # LOAD ORDER ITEMS
        # ====================================================

        items_result = await db.execute(
            select(OrderItem)
            .options(
                selectinload(
                    OrderItem.item
                )
            )
            .where(
                OrderItem.order_id == order.id
            )
        )

        order_items = (
            items_result.scalars().all()
        )

        # ====================================================
        # TABLE NAME
        # ====================================================

        table_name = None

        if order.table_id:

            table = await db.get(
                Table,
                order.table_id,
            )

            if table:

                table_name = table.name

                if table.floor:

                    table_name = (
                        f"{table.name} "
                        f"({table.floor})"
                    )

        # ====================================================
        # RESPONSE
        # ====================================================

        return {
            "id": order.id,

            "client_id": order.client_id,

            "branch_id": order.branch_id,

            "table_id": order.table_id,

            "table_name": table_name,

            "order_type": order.order_type,

            "customer_name": order.customer_name,

            "customer_phone": order.customer_phone,

            "notes": order.notes,

            "status": order.status,

            "total_amount": float(
                order.total_amount or 0.0
            ),

            "created_at": order.created_at,

            "items": [
                {
                    "id": item.id,

                    "item_id": item.item_id,

                    "item_name": (
                        item.item.name
                        if item.item
                        else None
                    ),

                    "quantity": item.quantity,

                    "price": getattr(
                        item,
                        "price",
                        None,
                    ),

                    "order_status": (
                        item.order_status
                    ),
                }
                for item in order_items
            ],
        }

    except HTTPException:

        await db.rollback()
        raise

    except SQLAlchemyError as e:

        await db.rollback()

        print(
            "UPDATE ORDER DB ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Database error while "
                "updating order"
            ),
        )

    except Exception as e:

        await db.rollback()

        print(
            "UPDATE ORDER ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected error occurred"
            ),
        )


# ============================================================
# CANCEL ORDER
# ============================================================


@router.patch(
    "/cancel_order/{order_id}"
)
async def cancel_order(
    order_id: int,
    db: SessionDep,
    current=Depends(access_one),
):

    try:

        # ----------------------------------------------------
        # GET ORDER
        # ----------------------------------------------------

        result = await db.execute(
            select(Order)
            .where(
                Order.id == order_id
            )
        )

        order = (
            result.scalar_one_or_none()
        )

        if not order:

            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        # ----------------------------------------------------
        # ACCESS
        # ----------------------------------------------------

        await get_client_if_accessible(
            order.client_id,
            db,
            current,
        )

        if (
            current["role"]
            == UserRole.STAFF
            and
            order.branch_id
            != current["user"].branch_id
        ):

            raise HTTPException(
                status_code=403,
                detail=(
                    "Not allowed to cancel "
                    "order from another branch"
                ),
            )

        # ----------------------------------------------------
        # STATUS CHECK
        # ----------------------------------------------------

        current_status = str(
            order.status
        ).lower()

        if current_status == "cancelled":

            raise HTTPException(
                status_code=400,
                detail=(
                    "Order already cancelled"
                ),
            )

        if current_status == "served":

            raise HTTPException(
                status_code=400,
                detail=(
                    "Served orders cannot "
                    "be cancelled"
                ),
            )

        # ----------------------------------------------------
        # TABLE
        # ----------------------------------------------------

        if order.table_id:

            table = await db.get(
                Table,
                order.table_id,
            )

            if table:

                table.status = (
                    TableStatus.available
                )

                await Cache.delete(
                    f"tables:branch:"
                    f"{table.branch_id}"
                )

        # ----------------------------------------------------
        # CANCEL ORDER
        # ----------------------------------------------------

        order.status = "cancelled"

        # ----------------------------------------------------
        # DELETE CUSTOMER HISTORY
        # ----------------------------------------------------

        await db.execute(
            delete(
                CustomerVisitHistory
            )
            .where(
                CustomerVisitHistory.order_id
                == order.id
            )
        )

        # ----------------------------------------------------
        # RECALCULATE CUSTOMER
        #
        # Cancelled order is automatically
        # excluded by recalculate_customer_crm().
        # ----------------------------------------------------

        customer = None

        if order.customer_id:

            customer = await db.get(
                Customer,
                order.customer_id,
            )

            if customer:

                await recalculate_customer_crm(
                    db=db,
                    customer_id=customer.id,
                    branch_id=order.branch_id,
                )

        await db.commit()

        await db.refresh(order)

        if customer:
            await db.refresh(customer)

        # ----------------------------------------------------
        # CACHE
        # ----------------------------------------------------

        await Cache.delete(
            f"kitchen:branch:"
            f"{order.branch_id}"
        )

        return {
            "message":
                "Order cancelled successfully",

            "order_id":
                order.id,

            "status":
                order.status,

            "customer_id": (
                customer.id
                if customer
                else None
            ),

            "customer_total_spend": (
                float(
                    customer.total_spend
                    or 0.0
                )
                if customer
                else None
            ),

            "customer_rank": (
                customer.current_rank
                if customer
                else None
            ),

            "loyalty_points": (
                float(
                    customer.loyalty_points
                    or 0.0
                )
                if customer
                else None
            ),
        }

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError as e:

        await db.rollback()

        print(
            "CANCEL ORDER DB ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Database error while "
                "cancelling order"
            ),
        )

    except Exception as e:

        await db.rollback()

        print(
            "CANCEL ORDER ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected error while "
                "cancelling order"
            ),
        )


# ============================================================
# UPDATE ORDER ITEM STATUS
# ============================================================


@router.patch(
    "/order_item_status/{order_id}/{item_id}",
    response_model=OrderItemStatusResponse,
)
async def update_order_item_status(
    order_id: int,
    item_id: int,
    data: OrderItemStatusUpdate,
    db: SessionDep,
    current=Depends(access_one),
):

    try:

        valid_statuses = [
            "pending",
            "preparing",
            "ready",
            "served",
        ]

        new_status = (
            str(
                data.order_status
            )
            .lower()
            .strip()
        )

        if new_status not in valid_statuses:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Allowed statuses: "
                    f"{valid_statuses}"
                ),
            )

        # ----------------------------------------------------
        # ORDER
        # ----------------------------------------------------

        result = await db.execute(
            select(Order)
            .where(
                Order.id == order_id
            )
        )

        order = (
            result.scalar_one_or_none()
        )

        if not order:

            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        await get_client_if_accessible(
            order.client_id,
            db,
            current,
        )

        if (
            current["role"]
            == UserRole.STAFF
            and
            order.branch_id
            != current["user"].branch_id
        ):

            raise HTTPException(
                status_code=403,
                detail=(
                    "Not allowed for "
                    "another branch"
                ),
            )

        # ----------------------------------------------------
        # ORDER ITEM
        # ----------------------------------------------------

        item_result = await db.execute(
            select(OrderItem)
            .where(
                OrderItem.item_id
                == item_id,

                OrderItem.order_id
                == order_id,
            )
        )

        order_item = (
            item_result
            .scalar_one_or_none()
        )

        if not order_item:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Order item not found "
                    "in this order"
                ),
            )

        old_status = (
            str(
                order_item.order_status
            )
            .lower()
            .strip()
        )

        # ----------------------------------------------------
        # INVENTORY
        #
        # Only consume once:
        #
        # pending -> preparing
        #
        # NOT:
        #
        # preparing -> ready
        # ready -> served
        # ----------------------------------------------------

        if (
            old_status == "pending"
            and
            new_status == "preparing"
        ):

            await consume_inventory_for_item(
                db=db,
                item_id=order_item.item_id,
                quantity=order_item.quantity,
            )

        order_item.order_status = (
            new_status
        )

        await db.flush()

        # ----------------------------------------------------
        # GET ALL ITEM STATUSES
        # ----------------------------------------------------

        all_items_result = await db.execute(
            select(OrderItem)
            .where(
                OrderItem.order_id
                == order_id
            )
        )

        all_items = (
            all_items_result
            .scalars()
            .all()
        )

        statuses = [
            str(
                item.order_status
            )
            .lower()
            .strip()
            for item in all_items
        ]

        # ----------------------------------------------------
        # ORDER STATUS
        # ----------------------------------------------------

        if statuses and all(
            status == "served"
            for status in statuses
        ):

            order.status = "served"

        elif statuses and all(
            status in (
                "ready",
                "served",
            )
            for status in statuses
        ):

            order.status = "ready"

        elif any(
            status == "preparing"
            for status in statuses
        ):

            order.status = "preparing"

        elif any(
            status == "ready"
            for status in statuses
        ):

            order.status = "ready"

        else:

            order.status = "pending"

        await db.commit()

        await db.refresh(
            order_item
        )

        await Cache.delete(
            f"kitchen:branch:"
            f"{order.branch_id}"
        )

        return {
            "id":
                order_item.id,

            "order_id":
                order_item.order_id,

            "item_id":
                order_item.item_id,

            "quantity":
                order_item.quantity,

            "order_status":
                order_item.order_status,
        }

    except HTTPException:

        await db.rollback()

        raise

    except SQLAlchemyError as e:

        await db.rollback()

        print(
            "ORDER ITEM STATUS DB ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Database error: {str(e)}"
            ),
        )

    except Exception as e:

        await db.rollback()

        print(
            "ORDER ITEM STATUS ERROR:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unexpected error: {str(e)}"
            ),
        )


# ============================================================
# ALL BRANCHES - ORDERS
# ============================================================


@router.get(
    "/dashboard/all-branches"
)
async def orders_all_branches(
    db: SessionDep,
    client_id: int | None = Query(None),
    current=Depends(access_one),
):

    role = current["role"]
    user = current["user"]

    if role.name == "CLIENT":

        effective_client_id = (
            client_id
            or getattr(
                user,
                "id",
                None,
            )
        )

    else:

        effective_client_id = (
            client_id
            or getattr(
                user,
                "client_id",
                None,
            )
            or getattr(
                user,
                "id",
                None,
            )
        )

    if not effective_client_id:

        raise HTTPException(
            status_code=400,
            detail=(
                "client_id is required"
            ),
        )

    await get_client_if_accessible(
        effective_client_id,
        db,
        current,
    )

    return await get_orders_all_branches(
        db=db,
        client_id=effective_client_id,
    )


# ============================================================
# ALL BRANCHES - MENU
# ============================================================


@router.get(
    "/menu/dashboard/all-branches"
)
async def menu_all_branches(
    db: SessionDep,
    client_id: int | None = Query(None),
    current=Depends(access_one),
):

    role = current["role"]
    user = current["user"]

    if role.name not in [
        "CLIENT",
        "PARTNER",
    ]:

        raise HTTPException(
            status_code=403,
            detail="Not allowed",
        )

    # --------------------------------------------------------
    # CLIENT
    # --------------------------------------------------------

    if role.name == "CLIENT":

        effective_client_id = (
            client_id
            or getattr(
                user,
                "id",
                None,
            )
        )

    # --------------------------------------------------------
    # PARTNER
    # --------------------------------------------------------

    else:

        effective_client_id = (
            client_id
            or getattr(
                user,
                "client_id",
                None,
            )
        )

    if not effective_client_id:

        raise HTTPException(
            status_code=400,
            detail=(
                "client_id is required"
            ),
        )

    await get_client_if_accessible(
        effective_client_id,
        db,
        current,
    )

    return await get_menu_all_branches(
        db=db,
        client_id=effective_client_id,
    )