from datetime import datetime
from sqlalchemy import func
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from app.db.config import SessionDep
from app.accounts.deps import (
    access_one,
    UserRole,
    calculate_status
)
from app.accounts.inventory.model import (
    InventoryItem,
    Godown
)
from app.accounts.branch.model import Branch
from app.accounts.purchaseorder.model import (
    PurchaseOrder,
    PurchaseOrderItem
)
from app.accounts.purchaseorder.schema import (
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    ReceiveStockRequest,
)
router = APIRouter(
    prefix="/purchase-orders",
    tags=["Purchase Orders"]
)
@router.post("/create")
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: SessionDep,
    current=Depends(access_one)
):
    branch = await db.get(Branch, data.branch_id)

    if not branch:
        raise HTTPException(404, "Branch not found")

    godown = await db.get(Godown, data.godown_id)

    if not godown:
        raise HTTPException(404, "Godown not found")

    if godown.branch_id != data.branch_id:
        raise HTTPException(400, "Godown does not belong to branch")

    total_amount = 0

    for item in data.items:
        total_amount += item.quantity * item.unit_price

    po_number = f"PO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    purchase_order = PurchaseOrder(
        branch_id=data.branch_id,
        godown_id=data.godown_id,
        po_number=po_number,
        vendor_name=data.vendor_name,
        vendor_phone=data.vendor_phone,
        notes=data.notes,
        total_amount=total_amount
    )

    db.add(purchase_order)
    await db.flush()

    for item in data.items:
        po_item = PurchaseOrderItem(
            purchase_order_id=purchase_order.id,
            inventory_item_id=item.inventory_item_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.quantity * item.unit_price
        )
        db.add(po_item)

    await db.commit()
    await db.refresh(purchase_order)

    return {
        "message": "Purchase order created successfully",
        "purchase_order_id": purchase_order.id,
        "po_number": purchase_order.po_number,
        "total_amount": total_amount
    }

@router.get("/dashboard/summary")
async def purchase_order_summary(
    db: SessionDep
):
    result = await db.execute(
        select(
            PurchaseOrder.status,
            func.count(PurchaseOrder.id)
        ).group_by(
            PurchaseOrder.status
        )
    )

    rows = result.all()

    summary = {
        "total_po": 0,
        "pending": 0,
        "approved": 0,
        "ordered": 0,
        "partially_received": 0,
        "received": 0,
        "cancelled": 0
    }

    for status, count in rows:
        summary["total_po"] += count

        if status in summary:
            summary[status] = count

    return summary



@router.get("/reports")
async def purchase_report(
    start_date: datetime,
    end_date: datetime,
    db: SessionDep
):
    result = await db.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.created_at >= start_date,
            PurchaseOrder.created_at <= end_date
        )
    )

    orders = result.scalars().all()

    total_amount = sum(
        po.total_amount
        for po in orders
    )

    return {
        "total_orders": len(orders),
        "total_purchase_amount": total_amount,
        "orders": orders
    }



@router.get("/vendor-report")
async def vendor_report(
    db: SessionDep
):
    result = await db.execute(
        select(
            PurchaseOrder.vendor_name,
            func.count(
                PurchaseOrder.id
            ),
            func.sum(
                PurchaseOrder.total_amount
            )
        ).group_by(
            PurchaseOrder.vendor_name
        )
    )

    rows = result.all()

    return [
        {
            "vendor_name": row[0],
            "total_orders": row[1],
            "total_amount": row[2]
        }
        for row in rows
    ]



@router.get("/reorder-suggestions")
async def reorder_suggestions(
    db: SessionDep
):
    result = await db.execute(
        select(InventoryItem).where(
            InventoryItem.stock_qty
            <= InventoryItem.reorder_level
        )
    )

    items = result.scalars().all()

    return [
        {
            "inventory_item_id": item.id,
            "item_name": item.name,
            "current_stock": item.stock_qty,
            "reorder_level": item.reorder_level
        }
        for item in items
    ]

@router.get("/list")
async def get_purchase_orders(
    db: SessionDep,
    page: int = 1,
    size: int = 20,
    branch_id: int | None = None,
    status: str | None = None,
    current=Depends(access_one)
):
    role = current["role"]
    user = current["user"]

    if page < 1:
        page = 1

    if size < 1:
        size = 20

    if role == UserRole.STAFF:
        branch_id = user.branch_id

    query = select(PurchaseOrder)

    if branch_id:
        query = query.where(
            PurchaseOrder.branch_id == branch_id
        )

    if status:
        query = query.where(
            PurchaseOrder.status == status
        )

    offset = (page - 1) * size

    query = (
        query
        .offset(offset)
        .limit(size)
    )

    result = await db.execute(query)

    orders = result.scalars().all()

    return {
        "page": page,
        "size": size,
        "count": len(orders),
        "data": orders
    }


@router.get("/{purchase_order_id}")
async def get_purchase_order_detail(
    purchase_order_id: int,
    db: SessionDep
):
    purchase_order = await db.get(PurchaseOrder, purchase_order_id)

    if not purchase_order:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found"
        )

    result = await db.execute(
        select(PurchaseOrderItem).where(
            PurchaseOrderItem.purchase_order_id == purchase_order_id
        )
    )

    items = result.scalars().all()

    return {
        "id": purchase_order.id,
        "po_number": purchase_order.po_number,
        "vendor_name": purchase_order.vendor_name,
        "vendor_phone": purchase_order.vendor_phone,
        "status": purchase_order.status,
        "total_amount": purchase_order.total_amount,
        "created_at": purchase_order.created_at,
        "items": items
    }


def validate_status_transition(current_status: str, new_status: str):
    transitions = {
        "pending": ["approved", "cancelled"],
        "approved": ["ordered", "cancelled"],
        "ordered": ["partially_received", "received"],
        "partially_received": ["received"]
    }

    allowed = transitions.get(current_status, [])

    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move {current_status} to {new_status}"
        )


@router.patch("/{po_id}/approve")
async def approve_purchase_order(
    po_id: int,
    db: SessionDep
):
    po = await db.get(PurchaseOrder, po_id)

    if not po:
        raise HTTPException(404, "Purchase order not found")

    validate_status_transition(po.status, "approved")
    po.status = "approved"

    await db.commit()

    return {"message": "Purchase order approved"}


@router.patch("/{po_id}/ordered")
async def mark_purchase_order_ordered(
    po_id: int,
    db: SessionDep
):
    po = await db.get(PurchaseOrder, po_id)

    if not po:
        raise HTTPException(404, "Purchase order not found")

    validate_status_transition(po.status, "ordered")
    po.status = "ordered"

    await db.commit()

    return {"message": "Purchase order marked ordered"}


@router.patch("/{po_id}/cancel")
async def cancel_purchase_order(
    po_id: int,
    db: SessionDep
):
    po = await db.get(PurchaseOrder, po_id)

    if not po:
        raise HTTPException(404, "Purchase order not found")

    if po.status in ["received", "partially_received"]:
        raise HTTPException(400, "Cannot cancel received PO")

    po.status = "cancelled"

    await db.commit()

    return {"message": "Purchase order cancelled"}


@router.patch("/{po_id}/receive")
async def receive_purchase_order(
    po_id: int,
    data: ReceiveStockRequest,
    db: SessionDep
):
    po = await db.get(PurchaseOrder, po_id)

    if not po:
        raise HTTPException(
            status_code=404,
            detail="Purchase order not found"
        )

    if po.status not in ["ordered", "partially_received"]:
        raise HTTPException(
            status_code=400,
            detail="PO not ready for receiving"
        )

    for row in data.items:
        po_item = await db.get(PurchaseOrderItem, row.purchase_order_item_id)

        if not po_item:
            raise HTTPException(
                status_code=404,
                detail="PO item not found"
            )

        if po_item.purchase_order_id != po.id:
            raise HTTPException(
                status_code=400,
                detail="PO item does not belong to this purchase order"
            )

        if row.received_qty <= 0:
            raise HTTPException(
                status_code=400,
                detail="Received quantity must be greater than zero"
            )

        remaining_qty = po_item.quantity - po_item.received_qty

        if row.received_qty > remaining_qty:
            raise HTTPException(
                status_code=400,
                detail="Received quantity exceeds ordered quantity"
            )

        inventory = await db.get(InventoryItem, po_item.inventory_item_id)

        if not inventory:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found"
            )

        if inventory.godown_id != po.godown_id:
            raise HTTPException(
                status_code=400,
                detail="Inventory item belongs to different godown"
            )

        inventory.stock_qty += row.received_qty
        inventory.status = calculate_status(
            inventory.stock_qty,
            inventory.reorder_level
        )
        inventory.last_restocked = datetime.utcnow()
        po_item.received_qty += row.received_qty

    await db.flush()

    result = await db.execute(
        select(PurchaseOrderItem).where(
            PurchaseOrderItem.purchase_order_id == po_id
        )
    )

    items = result.scalars().all()

    fully_received = all(
        item.received_qty >= item.quantity for item in items
    )

    if fully_received:
        po.status = "received"
    else:
        po.status = "partially_received"

    await db.commit()

    return {
        "message": "Stock received successfully",
        "status": po.status
    }


@router.patch("/{po_id}")
async def update_purchase_order(
    po_id: int,
    data: PurchaseOrderUpdate,
    db: SessionDep
):
    po = await db.get(
        PurchaseOrder,
        po_id
    )

    if not po:
        raise HTTPException(
            404,
            "Purchase order not found"
        )

    if po.status != "pending":
        raise HTTPException(
            400,
            "Only pending PO can be edited"
        )

    po.vendor_name = data.vendor_name
    po.vendor_phone = data.vendor_phone
    po.notes = data.notes

    result = await db.execute(
        select(PurchaseOrderItem).where(
            PurchaseOrderItem.purchase_order_id == po.id
        )
    )

    old_items = result.scalars().all()

    for item in old_items:
        await db.delete(item)

    total_amount = 0

    for item in data.items:
        subtotal = (
            item.quantity *
            item.unit_price
        )

        total_amount += subtotal

        db.add(
            PurchaseOrderItem(
                purchase_order_id=po.id,
                inventory_item_id=item.inventory_item_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=subtotal
            )
        )

    po.total_amount = total_amount

    await db.commit()

    return {
        "message":
        "Purchase order updated successfully"
    }


@router.delete("/{po_id}")
async def delete_purchase_order(
    po_id: int,
    db: SessionDep
):
    po = await db.get(
        PurchaseOrder,
        po_id
    )

    if not po:
        raise HTTPException(
            404,
            "Purchase order not found"
        )

    if po.status != "pending":
        raise HTTPException(
            400,
            "Only pending PO can be deleted"
        )

    await db.delete(po)

    await db.commit()

    return {
        "message":
        "Purchase order deleted successfully"
    }