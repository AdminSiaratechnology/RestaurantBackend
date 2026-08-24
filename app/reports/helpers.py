# app/reports/helpers.py

from datetime import date, datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.accounts.branch.model import Branch
from app.accounts.client.model import Client


def resolve_date_range(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    time_range: Optional[str] = None,
) -> Tuple[date, date]:
    """
    Standard date range resolver across all reports.
    Supports 'today', '7d'/'last_7_days', 'month'/'this_month', and custom ranges.
    Defaults to current month (first day of month to today).
    """
    today = date.today()
    if time_range == "today":
        return today, today
    elif time_range in ("7d", "last_7_days"):
        return today - timedelta(days=6), today
    elif time_range in ("month", "this_month"):
        return today.replace(day=1), today
    elif from_date is not None and to_date is not None:
        if from_date > to_date:
            raise HTTPException(
                status_code=400,
                detail="from_date must be less than or equal to to_date",
            )
        return from_date, to_date
    elif from_date is not None:
        return from_date, today
    elif to_date is not None:
        return today.replace(day=1), to_date
    else:
        return today - timedelta(days=6), today  # Default to last 7 days for rich initial view


async def validate_and_get_scope(
    db: AsyncSession,
    client_id: Optional[int] = None,
    branch_id: Optional[int] = None,
) -> Tuple[Optional[Client], List[Branch], Dict[str, Any]]:
    """
    Validates client and branch access.
    - If branch_id is provided, checks if it belongs to client_id (if client_id is given).
    - If branch_id is omitted, returns all branches for client_id.
    - Returns (client, branches, scope_dict).
    """
    client: Optional[Client] = None
    branches: List[Branch] = []

    if client_id is not None:
        client_res = await db.execute(select(Client).where(Client.id == client_id))
        client = client_res.scalar_one_or_none()
        if not client:
            raise HTTPException(
                status_code=404,
                detail=f"Client with ID {client_id} not found",
            )

    if branch_id is not None:
        branch_query = select(Branch).where(Branch.id == branch_id)
        if client_id is not None:
            branch_query = branch_query.where(Branch.client_id == client_id)

        branch_res = await db.execute(branch_query)
        branch = branch_res.scalar_one_or_none()
        if not branch:
            if client_id is not None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Branch ID {branch_id} does not belong to Client ID {client_id}",
                )
            raise HTTPException(
                status_code=404,
                detail=f"Branch with ID {branch_id} not found",
            )
        branches = [branch]
        if client is None and branch.client_id:
            c_res = await db.execute(select(Client).where(Client.id == branch.client_id))
            client = c_res.scalar_one_or_none()
    elif client_id is not None:
        # All branches for client
        b_res = await db.execute(
            select(Branch).where(Branch.client_id == client_id).order_by(Branch.id.asc())
        )
        branches = list(b_res.scalars().all())
    else:
        # Fallback default: first branch if nothing specified
        b_res = await db.execute(select(Branch).order_by(Branch.id.asc()).limit(1))
        first_branch = b_res.scalar_one_or_none()
        if first_branch:
            branches = [first_branch]
            if first_branch.client_id:
                c_res = await db.execute(select(Client).where(Client.id == first_branch.client_id))
                client = c_res.scalar_one_or_none()

    is_all_branches = branch_id is None and len(branches) > 1

    if is_all_branches:
        branch_name_display = "All Branches"
        scope_name = (
            f"Client: {client.name} (All {len(branches)} Branches)"
            if client
            else f"All Branches ({len(branches)} Branches)"
        )
    elif len(branches) == 1:
        b = branches[0]
        branch_name_display = b.name
        scope_name = f"Branch: {b.name} (ID: {b.id})"
        if client:
            scope_name = f"Client: {client.name} | Branch: {b.name} (ID: {b.id})"
    else:
        branch_name_display = "No Branch"
        scope_name = f"Client: {client.name}" if client else "General Scope"

    scope_meta = {
        "client_id": client.id if client else (branches[0].client_id if branches else None),
        "client_name": client.name if client else None,
        "branch_id": branch_id if (branch_id and not is_all_branches) else None,
        "branch_name": branch_name_display,
        "is_all_branches": is_all_branches,
        "total_branches": len(branches),
        "branch_ids": [b.id for b in branches],
        "scope_name": scope_name,
    }

    return client, branches, scope_meta


def safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        f = float(val)
        return 0.0 if (f != f) else f  # NaN check
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def safe_str(val: Any, default: str = "—") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s else default


def build_standard_chart_slots(time_range: str, from_date: date, to_date: date) -> List[Dict[str, Any]]:
    """
    Build default continuous dates or slot templates for charts so charts never have gaps.
    """
    today = date.today()
    if time_range == "today" or (from_date == to_date and from_date == today):
        time_slots = [
            ("9 AM", 0, 9),
            ("12 PM", 9, 12),
            ("3 PM", 12, 15),
            ("6 PM", 15, 18),
            ("9 PM", 18, 21),
            ("11 PM", 21, 24),
        ]
        return [{"label": slot[0], "date": str(today), "amount": 0.0, "quantity": 0.0} for slot in time_slots]
    elif time_range in ("month", "this_month"):
        weeks_def = [
            ("Week 1", 1, 7),
            ("Week 2", 8, 14),
            ("Week 3", 15, 21),
            ("Week 4", 22, 28),
            ("Week 5", 29, 31),
        ]
        return [{"label": w[0], "amount": 0.0, "quantity": 0.0} for w in weeks_def]
    else:
        # Daily range
        delta = (to_date - from_date).days
        delta = min(max(delta, 0), 60)  # cap to 60 days
        slots = []
        for i in range(delta + 1):
            curr = from_date + timedelta(days=i)
            if curr == today:
                lbl = "Today"
            elif curr == today - timedelta(days=1):
                lbl = "Yesterday"
            else:
                lbl = curr.strftime("%d-%m")
            slots.append({"date": str(curr), "label": lbl, "amount": 0.0, "quantity": 0.0})
        return slots
