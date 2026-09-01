# app/reports/router.py

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_db
from app.accounts.deps import get_current_user, UserRole
from app.accounts.staff.model import StaffRole
from app.accounts.permission.model import StaffPermission
from app.core.cache import Cache
from sqlalchemy import select
from app.reports.sales.service import SalesReportService
from app.reports.purchase.service import PurchaseReportService
from app.reports.inventory.service import InventoryReportService
from app.reports.payment.service import PaymentReportService
from app.reports.financial.service import FinancialReportService
from app.reports.category.service import CategoryReportService
from app.reports.item.service import ItemReportService
from app.reports.customer.service import CustomerReportService
from app.reports.order.service import OrderReportService
from app.reports.tax.service import TaxReportService

router = APIRouter(
    prefix="/reports",
    tags=["Standardized Reports"],
)

SERVICES = {
    "sale": SalesReportService,
    "sales": SalesReportService,
    "purchase": PurchaseReportService,
    "purchases": PurchaseReportService,
    "inventory": InventoryReportService,
    "inventories": InventoryReportService,
    "payment": PaymentReportService,
    "payments": PaymentReportService,
    "financial": FinancialReportService,
    "financials": FinancialReportService,
    "category": CategoryReportService,
    "categories": CategoryReportService,
    "item": ItemReportService,
    "items": ItemReportService,
    "customer": CustomerReportService,
    "customers": CustomerReportService,
    "order": OrderReportService,
    "orders": OrderReportService,
    "tax": TaxReportService,
    "taxes": TaxReportService,
}


async def check_report_staff_permission(report_type: str, user, role, db: AsyncSession):
    if role != UserRole.STAFF:
        return

    if getattr(user, "role", None) in (StaffRole.chef, StaffRole.waiter):
        raise HTTPException(status_code=403, detail="Reports access denied for this staff role")

    cache_key = f"permissions:user:{user.id}"
    perms = await Cache.get(cache_key)
    if not perms:
        res = await db.execute(select(StaffPermission).where(StaffPermission.staff_id == user.id))
        p = res.scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=403, detail="No permissions assigned")
        perms = {c.name: getattr(p, c.name) for c in p.__table__.columns}
        await Cache.set(cache_key, perms, expire=1800)

    if not perms.get("manage_reports", False):
        raise HTTPException(status_code=403, detail="manage_reports permission denied")

    if report_type.lower() in ("purchase", "purchases") and not perms.get("manage_purchase", False):
        raise HTTPException(status_code=403, detail="manage_purchase permission denied")


@router.get("/unified/{report_type}")
async def get_unified_report(
    report_type: str,
    client_id: Optional[int] = Query(None, description="Client ID"),
    branch_id: Optional[int] = Query(None, description="Branch ID (omit for all branches)"),
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    time_range: Optional[str] = Query(None, description="Time range: today, 7d, month, custom"),
    category: Optional[str] = Query(None, description="Category filter"),
    category_id: Optional[int] = Query(None, description="Category ID"),
    godown_id: Optional[int] = Query(None, description="Godown ID"),
    supplier_id: Optional[int] = Query(None, description="Supplier / Vendor ID"),
    customer_type: Optional[str] = Query(None, description="Customer Type"),
    payment_method: Optional[str] = Query(None, description="Payment Method"),
    order_type: Optional[str] = Query(None, description="Order Type"),
    status: Optional[str] = Query(None, description="Status filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    key = report_type.lower()
    await check_report_staff_permission(key, current["user"], current["role"], db)

    service_cls = SERVICES.get(key)
    if not service_cls:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown report type: '{report_type}'. Available: {list(SERVICES.keys())}",
        )

    # Build kwargs supported by the specific service
    kwargs = {
        "db": db,
        "client_id": client_id,
        "branch_id": branch_id,
        "from_date": from_date,
        "to_date": to_date,
        "time_range": time_range,
        "page": page,
        "page_size": page_size,
    }

    if key in ("sale", "sales"):
        kwargs["payment_method"] = payment_method
        kwargs["order_type"] = order_type
    elif key in ("purchase", "purchases"):
        kwargs["supplier_id"] = supplier_id
    elif key in ("inventory", "inventories"):
        kwargs["category"] = category
        kwargs["godown_id"] = godown_id
        kwargs["status_filter"] = status
    elif key in ("payment", "payments"):
        kwargs["payment_method"] = payment_method
    elif key in ("item", "items"):
        kwargs["category_id"] = category_id
    elif key in ("customer", "customers"):
        kwargs["customer_type"] = customer_type
    elif key in ("order", "orders"):
        kwargs["order_type"] = order_type
        kwargs["status"] = status

    return await service_cls.get_report_data(**kwargs)


@router.get("/unified/{report_type}/export")
async def export_unified_report(
    report_type: str,
    client_id: Optional[int] = Query(None, description="Client ID"),
    branch_id: Optional[int] = Query(None, description="Branch ID (omit for all branches)"),
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    time_range: Optional[str] = Query(None, description="Time range: today, 7d, month, custom"),
    category: Optional[str] = Query(None, description="Category filter"),
    category_id: Optional[int] = Query(None, description="Category ID"),
    godown_id: Optional[int] = Query(None, description="Godown ID"),
    supplier_id: Optional[int] = Query(None, description="Supplier / Vendor ID"),
    customer_type: Optional[str] = Query(None, description="Customer Type"),
    payment_method: Optional[str] = Query(None, description="Payment Method"),
    order_type: Optional[str] = Query(None, description="Order Type"),
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    key = report_type.lower()
    await check_report_staff_permission(key, current["user"], current["role"], db)

    service_cls = SERVICES.get(key)
    if not service_cls:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown report type: '{report_type}'. Available: {list(SERVICES.keys())}",
        )

    kwargs = {
        "db": db,
        "client_id": client_id,
        "branch_id": branch_id,
        "from_date": from_date,
        "to_date": to_date,
        "time_range": time_range,
    }

    if key in ("sale", "sales"):
        kwargs["payment_method"] = payment_method
        kwargs["order_type"] = order_type
    elif key in ("purchase", "purchases"):
        kwargs["supplier_id"] = supplier_id
    elif key in ("inventory", "inventories"):
        kwargs["category"] = category
        kwargs["godown_id"] = godown_id
    elif key in ("payment", "payments"):
        kwargs["payment_method"] = payment_method
    elif key in ("item", "items"):
        kwargs["category_id"] = category_id
    elif key in ("customer", "customers"):
        kwargs["customer_type"] = customer_type
    elif key in ("order", "orders"):
        kwargs["order_type"] = order_type

    excel_buf, filename = await service_cls.export_excel(**kwargs)

    return StreamingResponse(
        excel_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# =========================================================================
# DIRECT DOMAIN-SPECIFIC CONVENIENCE ENDPOINTS
# =========================================================================

# --- SALES ---
@router.get("/sales/report")
@router.get("/sale/report")
async def get_sales_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    return await SalesReportService.get_report_data(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range, page=page, page_size=page_size
    )

@router.get("/sales/export")
@router.get("/sale/export")
async def export_sales_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    excel_buf, filename = await SalesReportService.export_excel(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range
    )
    return StreamingResponse(
        excel_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

# --- FINANCIAL ---
@router.get("/financial/report")
async def get_financial_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await FinancialReportService.get_report_data(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range
    )

@router.get("/financial/export")
async def export_financial_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    excel_buf, filename = await FinancialReportService.export_excel(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range
    )
    return StreamingResponse(
        excel_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

# --- INVENTORY ---
@router.get("/inventory/report")
async def get_inventory_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    godown_id: Optional[int] = Query(None),
    page: int = Query(1),
    page_size: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    return await InventoryReportService.get_report_data(
        db=db, client_id=client_id, branch_id=branch_id, category=category, godown_id=godown_id, page=page, page_size=page_size
    )

@router.get("/inventory/export")
async def export_inventory_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    godown_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    excel_buf, filename = await InventoryReportService.export_excel(
        db=db, client_id=client_id, branch_id=branch_id, category=category, godown_id=godown_id
    )
    return StreamingResponse(
        excel_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

# --- PAYMENTS ---
@router.get("/payments/report")
async def get_payment_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    return await PaymentReportService.get_report_data(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range, payment_method=payment_method, page=page, page_size=page_size
    )

@router.get("/payments/export")
async def export_payment_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    excel_buf, filename = await PaymentReportService.export_excel(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range, payment_method=payment_method
    )
    return StreamingResponse(
        excel_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )

# --- CATEGORIES ---
@router.get("/categories")
async def get_categories_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(50),
    db: AsyncSession = Depends(get_db),
):
    return await CategoryReportService.get_report_data(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range, search=search, page=page, page_size=page_size
    )

@router.get("/categories/summary")
async def get_categories_summary_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    data = await CategoryReportService.get_report_data(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range
    )
    return {
        "success": True,
        "scope": data["scope"],
        "summary": data["summary"],
    }

@router.get("/categories/chart")
async def get_categories_chart_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    data = await CategoryReportService.get_report_data(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range
    )
    return {
        "success": True,
        "scope": data["scope"],
        "chart": data["chart"],
        "top_items": data["top_items"],
    }

@router.get("/categories/export")
async def export_categories_report_endpoint(
    client_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    time_range: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    excel_buf, filename = await CategoryReportService.export_excel(
        db=db, client_id=client_id, branch_id=branch_id, from_date=from_date, to_date=to_date, time_range=time_range, search=search
    )
    return StreamingResponse(
        excel_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
