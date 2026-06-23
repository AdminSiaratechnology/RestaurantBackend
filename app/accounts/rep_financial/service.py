from sqlalchemy import select, func

from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.rep_financial.schema import (
    DashboardSummaryResponse,
    TaxCollectedResponse
)


async def dashboard_summary_service(
    db,
    branch_id: int
):
    revenue_result = await db.execute(
        select(
            func.coalesce(
                func.sum(Bill.grand_total),
                0
            )
        ).where(
            Bill.payment_status == PaymentStatus.complete,
            Bill.branch_id == branch_id
        )
    )

    orders_result = await db.execute(
        select(
            func.count(Bill.id)
        ).where(
            Bill.payment_status == PaymentStatus.complete,
            Bill.branch_id == branch_id
        )
    )

    total_revenue = revenue_result.scalar() or 0
    paid_orders = orders_result.scalar() or 0

    return DashboardSummaryResponse(
        total_revenue=round(float(total_revenue), 2),
        paid_orders=paid_orders
    )


async def get_tax_collected_service(
    db,
    branch_id: int
):
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    Bill.tax_total +
                    Bill.service_charge_amount
                ),
                0
            )
        ).where(
            Bill.payment_status == PaymentStatus.complete,
            Bill.branch_id == branch_id
        )
    )

    total_tax_collected = result.scalar() or 0

    return TaxCollectedResponse(
        total_tax_collected=round(
            float(total_tax_collected),
            2
        )
    )




from sqlalchemy import select, func

from app.accounts.branch.model import Branch
from app.accounts.bill.model import Bill
from app.accounts.bill.enum import PaymentStatus
from app.accounts.enum import UserRole
from fastapi import HTTPException


async def financial_dashboard_all_branches_service(
    db,
    current
):
    role = current["role"]
    user = current["user"]

    if role != UserRole.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == user.id
        )
    )

    branches = branches_result.scalars().all()

    branch_ids = [b.id for b in branches]

    if not branch_ids:
        return {
            "total_revenue": 0,
            "paid_orders": 0,
            "total_tax_collected": 0,
            "branches": []
        }

    response = {
        "total_revenue": 0,
        "paid_orders": 0,
        "total_tax_collected": 0,
        "branches": []
    }

    for branch in branches:

        revenue_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(Bill.grand_total),
                    0
                )
            ).where(
                Bill.branch_id == branch.id,
                Bill.payment_status == PaymentStatus.complete
            )
        )

        orders_result = await db.execute(
            select(
                func.count(Bill.id)
            ).where(
                Bill.branch_id == branch.id,
                Bill.payment_status == PaymentStatus.complete
            )
        )

        tax_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        Bill.tax_total +
                        Bill.service_charge_amount
                    ),
                    0
                )
            ).where(
                Bill.branch_id == branch.id,
                Bill.payment_status == PaymentStatus.complete
            )
        )

        revenue = float(revenue_result.scalar() or 0)
        orders = orders_result.scalar() or 0
        tax = float(tax_result.scalar() or 0)

        response["total_revenue"] += revenue
        response["paid_orders"] += orders
        response["total_tax_collected"] += tax

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,

            "total_revenue": round(revenue, 2),
            "paid_orders": orders,
            "total_tax_collected": round(tax, 2)
        })

    response["total_revenue"] = round(
        response["total_revenue"],
        2
    )

    response["total_tax_collected"] = round(
        response["total_tax_collected"],
        2
    )

    return response


# from sqlalchemy import select, func
# from fastapi import HTTPException

# from app.accounts.branch.model import Branch
# from app.accounts.bill.model import Bill
# from app.accounts.bill.enum import PaymentStatus
# from app.accounts.enum import UserRole


async def tax_collected_all_branches_service(
    db,
    current
):
    role = current["role"]
    user = current["user"]

    if role != UserRole.CLIENT:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == user.id
        )
    )

    branches = branches_result.scalars().all()

    if not branches:
        return {
            "total_tax_collected": 0,
            "branches": []
        }

    response = {
        "total_tax_collected": 0,
        "branches": []
    }

    for branch in branches:

        tax_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        Bill.tax_total +
                        Bill.service_charge_amount
                    ),
                    0
                )
            ).where(
                Bill.branch_id == branch.id,
                Bill.payment_status == PaymentStatus.complete
            )
        )

        tax_collected = float(
            tax_result.scalar() or 0
        )

        response["total_tax_collected"] += tax_collected

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "tax_collected": round(
                tax_collected,
                2
            )
        })

    response["total_tax_collected"] = round(
        response["total_tax_collected"],
        2
    )

    return response