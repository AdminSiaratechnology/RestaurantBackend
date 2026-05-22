from datetime import datetime, date, timedelta

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, not_, desc
from sqlalchemy.exc import SQLAlchemyError
from app.accounts.client.model import Client
from app.accounts.deps import access_two, access_three, access_four, get_client_if_accessible, require_super_admin
from app.accounts.deshboard.schema import TopClientOut
from app.accounts.enum import UserRole
from app.accounts.order.model import Order, OrderItem
from app.accounts.partner.model import Partner
from app.accounts.table.model import Table
from app.accounts.table.schema import TableStatus
from app.accounts.branch.model import Branch
from app.accounts.item.model import Item
from app.db.config import SessionDep










router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/today-revenue")
async def get_today_revenue(
    db: SessionDep,
    client_id: int | None = None,
    branch_id: int | None = None,
    current=Depends(access_four)
):
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            client_id = user.client_id
            branch_id = user.branch_id

        if not client_id or not branch_id:
            raise HTTPException(400, "client_id and branch_id are required")

        # ✅ Access control
        await get_client_if_accessible(client_id, db, current)

        # ✅ Today's range
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())

        # ✅ Revenue query
        result = await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0))
            .where(
                Order.client_id == client_id,
                Order.branch_id == branch_id,
                Order.status == "served",
                Order.created_at >= today_start,
                Order.created_at <= today_end
            )
        )

        total_revenue = result.scalar_one()

        return {
            "today_revenue": total_revenue
        }

    except SQLAlchemyError:
        raise HTTPException(
            500,
            "Database error while calculating revenue"
        )

    except Exception:
        raise HTTPException(
            500,
            "Unexpected error occurred"
        )





@router.get("/active-orders")
async def get_active_orders(
    db: SessionDep,
    client_id: int | None = None,
    branch_id: int | None = None,
    current=Depends(access_four)
):
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            client_id = user.client_id
            branch_id = user.branch_id

        if not client_id or not branch_id:
            raise HTTPException(400, "client_id and branch_id are required")

        # =========================
        # ✅ Access Control
        # =========================
        await get_client_if_accessible(
            client_id,
            db,
            current
        )

        # =========================
        # ✅ Active Orders Count
        # Active = pending/preparing/ready
        # Exclude = served/cancelled
        # =========================
        result = await db.execute(
            select(func.count(Order.id))
            .where(
                Order.client_id == client_id,
                Order.branch_id == branch_id,
                not_(
                    Order.status.in_([
                        "served",
                        "cancelled"
                    ])
                )
            )
        )

        active_orders = result.scalar() or 0

        return {
            "client_id": client_id,
            "branch_id": branch_id,
            "active_orders": active_orders
        }

    # =========================
    # ✅ Exception Handling
    # =========================
    except HTTPException as e:
        raise e

    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database error while fetching active orders"
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unexpected error occurred"
        )



@router.get("/occupied-tables")
async def get_occupied_tables(
    db: SessionDep,
    current=Depends(access_four)
):
    try:
        user = current["user"]
        role = current["role"]

        # ✅ Base condition
        conditions = []

        if role == UserRole.STAFF:
            conditions.append(Table.branch_id == user.branch_id)

        else:
            branch_result = await db.execute(
                select(Branch.id).where(Branch.client_id == user.id)
            )

            branch_ids = branch_result.scalars().all()

            if not branch_ids:
                return {
                    "occupied_tables": 0,
                    "total_tables": 0,
                    "display": "0/0"
                }

            conditions.append(Table.branch_id.in_(branch_ids))

        # ✅ Total tables count
        total_result = await db.execute(
            select(func.count(Table.id)).where(*conditions)
        )

        total_tables = total_result.scalar() or 0

        # ✅ Occupied tables count
        # occupied_result = await db.execute(
        #     select(func.count(Table.id)).where(
        #         *conditions,
        #         Table.status == TableStatus.occupied
        #     )
        # )

        # occupied_tables = occupied_result.scalar() or 0
        # ✅ Occupied tables count
        occupied_result = await db.execute(
            select(func.count(Table.id)).where(
                *conditions,
                Table.status == TableStatus.occupied
            )
        )

        occupied_tables = occupied_result.scalar() or 0

        return {
            "occupied_tables": occupied_tables,
            "total_tables": total_tables,
            "display": f"{occupied_tables}/{total_tables}"
        }

    except SQLAlchemyError as e:
        print("SQLAlchemy Error:", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    except Exception as e:
        print("Unexpected Error:", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    





@router.get("/menu-count")
async def get_menu_count(
    db: SessionDep,
    client_id: int | None = None,
    branch_id: int | None = None,
    current=Depends(access_four)
):
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            client_id = user.client_id
            branch_id = user.branch_id

        if not client_id or not branch_id:
            raise HTTPException(400, "client_id and branch_id are required")

        # Access check
        await get_client_if_accessible(client_id, db, current)

        # Count query (optimized)
        result = await db.execute(
            select(func.count(Item.id)).where(
                Item.client_id == client_id,
                Item.branch_id == branch_id
            )
        )

        count = result.scalar()

        return {
            "menu_items": count
        }

    except SQLAlchemyError:
        raise HTTPException(500, "Database error while counting menu items")
    





@router.get("/weekly-revenue")
async def get_weekly_revenue(
    db: SessionDep,
    client_id: int | None = None,
    branch_id: int | None = None,
    current=Depends(access_four)
):
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            client_id = user.client_id
            branch_id = user.branch_id

        if not client_id or not branch_id:
            raise HTTPException(400, "client_id and branch_id are required")

        # ✅ Access control
        await get_client_if_accessible(client_id, db, current)

        # ✅ Get last 7 days
        today = datetime.utcnow().date()
        week_start = today - timedelta(days=6)

        # ✅ Query: group by date
        result = await db.execute(
            select(
                func.date(Order.created_at).label("day"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue")
            )
            .where(
                Order.client_id == client_id,
                Order.branch_id == branch_id,
                Order.status == "served",
                Order.created_at >= week_start
            )
            .group_by(func.date(Order.created_at))
            .order_by(func.date(Order.created_at))
        )

        rows = result.all()

        # ✅ Convert to dict {date: revenue}
        revenue_map = {str(row.day): float(row.revenue) for row in rows}

        # ✅ Ensure all 7 days exist (important for graph)
        weekly_data = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            weekly_data.append({
                "day": day.strftime("%a"),  # Mon, Tue...
                "date": str(day),
                "revenue": revenue_map.get(str(day), 0)
            })

        return {
            "weekly_revenue": weekly_data
        }

    except SQLAlchemyError:
        raise HTTPException(500, "Database error while fetching weekly revenue")

    except Exception:
        raise HTTPException(500, "Unexpected error occurred")


@router.get("/top-items")
async def get_top_items(
    db: SessionDep,
    client_id: int | None = None,
    branch_id: int | None = None,
    current=Depends(access_four)
):
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            client_id = user.client_id
            branch_id = user.branch_id

        if not client_id or not branch_id:
            raise HTTPException(400, "client_id and branch_id are required")

        # ✅ Access control
        await get_client_if_accessible(client_id, db, current)

        # ✅ Aggregation query
        result = await db.execute(
            select(
                Item.id,
                Item.name,
                func.sum(OrderItem.quantity).label("total_orders"),
                func.avg(OrderItem.price).label("avg_price")
            )
            .join(OrderItem, OrderItem.item_id == Item.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Item.client_id == client_id,
                Item.branch_id == branch_id,
                Order.status == "served"   # 🔥 IMPORTANT
            )
            .group_by(Item.id, Item.name)
            .order_by(desc("total_orders"))
            .limit(5)
        )

        rows = result.all()

        # ✅ Format response
        top_items = []
        for idx, row in enumerate(rows, start=1):
            top_items.append({
                "rank": idx,
                "item_id": row.id,
                "name": row.name,
                "total_orders": int(row.total_orders),
                "price": float(row.avg_price or 0)
            })

        return {
            "top_items": top_items
        }

    except SQLAlchemyError:
        raise HTTPException(500, "Database error while fetching top items")

    except Exception:
        raise HTTPException(500, "Unexpected error occurred")

        

@router.get("/recent-orders")
async def get_recent_orders(
    db: SessionDep,
    limit: int = 5,   # default 5 like your UI
    client_id: int | None = None,
    branch_id: int | None = None,
    current=Depends(access_four)
):
    try:
        role = current["role"]
        user = current["user"]

        if role == UserRole.STAFF:
            client_id = user.client_id
            branch_id = user.branch_id

        if not client_id or not branch_id:
            raise HTTPException(400, "client_id and branch_id are required")

        # ✅ Access control
        await get_client_if_accessible(client_id, db, current)

        # ✅ Fetch latest orders
        result = await db.execute(
            select(Order)
            .where(
                Order.client_id == client_id,
                Order.branch_id == branch_id
            )
            .order_by(desc(Order.created_at))
            .limit(limit)
        )

        orders = result.scalars().all()

        # ✅ Format response
        recent_orders = []
        for idx, order in enumerate(orders, start=1):
            recent_orders.append({
                "rank": idx,
                "order_id": f"ORD-{order.id}",  # UI friendly
                "time": order.created_at.strftime("%I:%M %p"),  # 03:08 PM
                "status": order.status,
                "amount": float(order.total_amount)
            })

        return {
            "recent_orders": recent_orders
        }

    except SQLAlchemyError:
        raise HTTPException(500, "Database error while fetching recent orders")

    except Exception:
        raise HTTPException(500, "Unexpected error occurred")



@router.get("/partners/count")
async def get_partners_count(
    db: SessionDep,
    current=Depends(require_super_admin),
):
    result = await db.execute(
        select(func.count()).select_from(Partner)
    )
    count = result.scalar()

    return {
        "total_partners": count
    }





@router.get("/superadmin/partners")
async def partner_dashboard(
    db: SessionDep,
    current=Depends(require_super_admin)
):
    now = datetime.utcnow()



    # Today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59)

    # Yesterday
    yesterday_start = today_start - timedelta(days=1)
    yesterday_end = today_end - timedelta(days=1)

    # Last 7 Days
    last_7_start = today_start - timedelta(days=7)

    # Previous 7 Days
    prev_7_start = last_7_start - timedelta(days=7)
    prev_7_end = last_7_start


    def calculate_trend(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 2)

    def format_metric(value, trend, text):
        return {
            "value": value,
            "comparison": {
                "percentage": abs(trend),
                "is_positive": trend >= 0,
                "text": text
            }
        }




    # Total partners
    total_partners = (await db.execute(
        select(func.count()).select_from(Partner)
    )).scalar()

    # Active partners
    active_partners = (await db.execute(
        select(func.count()).where(Partner.is_active == True)
    )).scalar()

    # Today partners
    today_partners = (await db.execute(
        select(func.count()).where(
            Partner.created_at >= today_start,
            Partner.created_at <= today_end
        )
    )).scalar()

    # Yesterday partners
    yesterday_partners = (await db.execute(
        select(func.count()).where(
            Partner.created_at >= yesterday_start,
            Partner.created_at <= yesterday_end
        )
    )).scalar()

    # Last 7 days
    last_7_partners = (await db.execute(
        select(func.count()).where(Partner.created_at >= last_7_start)
    )).scalar()

    # Previous 7 days
    prev_7_partners = (await db.execute(
        select(func.count()).where(
            Partner.created_at >= prev_7_start,
            Partner.created_at < prev_7_end
        )
    )).scalar()



    active_percentage = 0
    if total_partners > 0:
        active_percentage = round((active_partners / total_partners) * 100, 2)

    today_trend = calculate_trend(today_partners, yesterday_partners)
    weekly_trend = calculate_trend(last_7_partners, prev_7_partners)



    graph = []
    for i in range(7):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)

        count = (await db.execute(
            select(func.count()).where(
                Partner.created_at >= day_start,
                Partner.created_at < day_end
            )
        )).scalar()

        graph.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count
        })

    graph.reverse()



    return {
        "total_partners": total_partners,

        "active_partners": {
            "value": active_partners,
            "percentage": active_percentage
        },

        "today_partners": format_metric(
            today_partners,
            today_trend,
            "vs yesterday"
        ),

        "last_7_days_partners": format_metric(
            last_7_partners,
            weekly_trend,
            "vs previous 7 days"
        ),

        "graph": graph
    }

@router.get("/superadmin/top-partners")
async def top_partners_dashboard(
    db: SessionDep,
    current=Depends(require_super_admin),
    limit: int = 5
):
    # =============================
    # GET TOP PARTNERS BY CLIENT COUNT
    # =============================

    result = await db.execute(
        select(
            Partner.id,
            Partner.name,
            func.count(Client.id).label("total_clients")
        )
        .join(Client, Client.partner_id == Partner.id)
        .group_by(Partner.id)
        .order_by(desc("total_clients"))
        .limit(limit)
    )

    partners = result.all()

    # =============================
    # FORMAT RESPONSE
    # =============================

    response = []
    rank = 1

    for p in partners:
        response.append({
            "rank": rank,
            "partner_id": p.id,
            "name": p.name,
            "total_clients": p.total_clients,

            # 🔥 FUTURE READY FIELDS
            "revenue": 0,   # you can add later
            "growth": 0     # you can add later
        })
        rank += 1

    return {
        "top_partners": response
    }




@router.get("/clients/top-performance", response_model=list[TopClientOut])
async def top_performing_clients(
    db: SessionDep,
    current=Depends(access_two),
    limit: int = 5
):
    now = datetime.utcnow()
    last_30_days = now - timedelta(days=30)
    prev_30_days = now - timedelta(days=60)

    # 🔐 Role filter
    client_filter = []
    if current["role"] == UserRole.PARTNER.value:
        client_filter.append(Client.partner_id == current["user"].id)

    # =========================
    # 🔥 CURRENT DATA (FIXED)
    # =========================
    current_data = await db.execute(
        select(
            Client.id,
            Client.name,
            func.count(Order.id).filter(
                Order.created_at >= last_30_days
            ).label("total_orders"),
            func.coalesce(
                func.sum(Order.total_amount).filter(
                    Order.created_at >= last_30_days
                ),
                0
            ).label("revenue")
        )
        .outerjoin(Order, Order.client_id == Client.id)   # ✅ FIX
        .where(*client_filter)
        .group_by(Client.id, Client.name)                # ✅ FIX
        .order_by(desc("revenue"))
        .limit(limit)
    )

    current_results = current_data.all()

    # =========================
    # 🔥 PREVIOUS DATA (FIXED RANGE)
    # =========================
    prev_data = await db.execute(
        select(
            Order.client_id,
            func.coalesce(func.sum(Order.total_amount), 0).label("prev_revenue")
        )
        .where(
            Order.created_at >= prev_30_days,
            Order.created_at < last_30_days   # ✅ better than between
        )
        .group_by(Order.client_id)
    )

    prev_map = {row.client_id: row.prev_revenue for row in prev_data}

    # =========================
    # ✅ RESPONSE
    # =========================
    response = []

    for idx, row in enumerate(current_results, start=1):
        prev_revenue = prev_map.get(row.id, 0)

        if prev_revenue > 0:
            growth = ((row.revenue - prev_revenue) / prev_revenue) * 100
        else:
            growth = 100 if row.revenue > 0 else 0

        response.append({
            "rank": idx,
            "client_id": row.id,
            "name": row.name,
            "total_orders": row.total_orders or 0,
            "revenue": float(row.revenue or 0),
            "growth": round(growth, 2)
        })

    return response



@router.get("/superadmin/new-partners")
async def new_partners_card(
    db: SessionDep,
    current=Depends(require_super_admin)
):
    now = datetime.utcnow()

    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)
    prev_30_days = now - timedelta(days=60)

    # ✅ New partners in last 7 days
    new_7_days_result = await db.execute(
        select(func.count(Partner.id))
        .where(Partner.created_at >= last_7_days)
    )
    new_7_days = new_7_days_result.scalar() or 0

    # ✅ New partners in last 30 days
    new_30_days_result = await db.execute(
        select(func.count(Partner.id))
        .where(Partner.created_at >= last_30_days)
    )
    new_30_days = new_30_days_result.scalar() or 0

    # ✅ Clients under partners created in last 30 days
    current_clients_result = await db.execute(
        select(func.count(Client.id))
        .join(Partner, Client.partner_id == Partner.id)
        .where(Partner.created_at >= last_30_days)
    )
    current_clients = current_clients_result.scalar() or 0

    # ✅ Clients under partners created in previous 30 days (30–60 days)
    prev_clients_result = await db.execute(
        select(func.count(Client.id))
        .join(Partner, Client.partner_id == Partner.id)
        .where(
            Partner.created_at >= prev_30_days,
            Partner.created_at < last_30_days
        )
    )
    prev_clients = prev_clients_result.scalar() or 0

    # ✅ Growth %
    if prev_clients == 0:
        growth = 100 if current_clients > 0 else 0
    else:
        growth = ((current_clients - prev_clients) / prev_clients) * 100

    return {
        "new_partners_7_days": new_7_days,
        "new_partners_30_days": new_30_days,
        "growth_percentage": round(growth, 2)
    }



@router.get("/superadmin/new-clients")
async def new_clients_card(
    db: SessionDep,
    current=Depends(require_super_admin)
):
    now = datetime.utcnow()

    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)
    prev_30_days = now - timedelta(days=60)

    # ✅ New clients in last 7 days
    new_7_days_result = await db.execute(
        select(func.count(Client.id))
        .where(Client.created_at >= last_7_days)
    )
    new_7_days = new_7_days_result.scalar() or 0

    # ✅ New clients in last 30 days
    new_30_days_result = await db.execute(
        select(func.count(Client.id))
        .where(Client.created_at >= last_30_days)
    )
    new_30_days = new_30_days_result.scalar() or 0

    # ✅ Clients in last 30 days
    current_clients_result = await db.execute(
        select(func.count(Client.id))
        .where(Client.created_at >= last_30_days)
    )
    current_clients = current_clients_result.scalar() or 0

    # ✅ Clients in previous 30 days (30–60 days)
    prev_clients_result = await db.execute(
        select(func.count(Client.id))
        .where(
            Client.created_at >= prev_30_days,
            Client.created_at < last_30_days
        )
    )
    prev_clients = prev_clients_result.scalar() or 0

    # ✅ Growth %
    if prev_clients == 0:
        growth = 100 if current_clients > 0 else 0
    else:
        growth = ((current_clients - prev_clients) / prev_clients) * 100

    return {
        "new_clients_7_days": new_7_days,
        "new_clients_30_days": new_30_days,
        "growth_percentage": round(growth, 2)
    }
