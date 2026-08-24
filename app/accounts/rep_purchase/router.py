from datetime import date
from typing import Optional
from sqlalchemy import select

from app.accounts.branch.model import Branch
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.config import get_db
from app.accounts.rep_purchase.service import PurchaseReportService
from app.accounts.deps import require_purchase_access


router = APIRouter(
    prefix="/purchase-reports",
    tags=["Purchase Reports"],
    dependencies=[Depends(require_purchase_access)],
)


@router.get("/branch/{branch_id}")
async def get_branch_purchase_report(
    branch_id: int,
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    time_range: Optional[str] = Query(None, description="Time range: today, 7d, month, custom"),
    supplier_id: Optional[int] = Query(None, description="Optional filter by supplier/vendor ID"),
    db: AsyncSession = Depends(get_db),
):

    try:

        report = await PurchaseReportService.get_branch_report(
            db=db,
            branch_id=branch_id,
            supplier_id=supplier_id,
            from_date=from_date,
            to_date=to_date,
            time_range=time_range,
        )

        return {
            "success": True,
            "data": report,
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate purchase report: {str(exc)}",
        )


@router.get("/branch/{branch_id}/export")
async def export_branch_purchase_report(
    branch_id: int,
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    time_range: Optional[str] = Query(None, description="Time range: today, 7d, month, custom"),
    supplier_id: Optional[int] = Query(None, description="Optional filter by supplier/vendor ID"),
    db: AsyncSession = Depends(get_db),
):

    try:

        excel_buf, filename = await PurchaseReportService.export_branch_report(
            db=db,
            branch_id=branch_id,
            from_date=from_date,
            to_date=to_date,
            time_range=time_range,
            supplier_id=supplier_id,
        )

        return StreamingResponse(
            excel_buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400 if "date" in str(exc).lower() else 404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to export branch purchase report: {str(exc)}",
        )


@router.get("/client/{client_id}/branches")
async def get_client_purchase_reports(
    client_id: int,
    db: AsyncSession = Depends(get_db),
):

    # --------------------------------------------------
    # GET CLIENT BRANCHES
    # --------------------------------------------------

    branch_result = await db.execute(
        select(Branch)
        .where(
            Branch.client_id == client_id
        )
        .order_by(Branch.id)
    )

    branches = branch_result.scalars().all()

    if not branches:

        return {
            "success": True,
            "data": {
                "client_id": client_id,
                "branches": [],
            },
        }

    # --------------------------------------------------
    # BUILD SEPARATE REPORT FOR EACH BRANCH
    # --------------------------------------------------

    branch_reports = []

    for branch in branches:

        report = await PurchaseReportService.get_branch_report(
            db=db,
            branch_id=branch.id,
        )

        branch_reports.append(
            {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "report": report,
            }
        )

    return {
        "success": True,
        "data": {
            "client_id": client_id,
            "total_branches": len(branches),
            "branches": branch_reports,
        },
    }


@router.get("/client/{client_id}/export")
async def export_client_purchase_report(
    client_id: int,
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    time_range: Optional[str] = Query(None, description="Time range: today, 7d, month, custom"),
    supplier_id: Optional[int] = Query(None, description="Optional filter by supplier/vendor ID"),
    branch_id: Optional[int] = Query(None, description="Optional branch ID under this client"),
    db: AsyncSession = Depends(get_db),
):

    try:

        excel_buf, filename = await PurchaseReportService.export_client_report(
            db=db,
            client_id=client_id,
            from_date=from_date,
            to_date=to_date,
            time_range=time_range,
            supplier_id=supplier_id,
            branch_id=branch_id,
        )

        return StreamingResponse(
            excel_buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400 if "date" in str(exc).lower() else 404,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to export client purchase report: {str(exc)}",
        )