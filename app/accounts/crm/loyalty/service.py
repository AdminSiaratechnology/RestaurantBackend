"""
app/accounts/crm/loyalty/service.py

Service layer for Customer Loyalty Accounts, Rank Calculation, Point Conversion,
and Loyalty Point Redemption.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import (
    select,
    or_,
    func,
)

from app.accounts.customer.model import Customer
from app.accounts.crm.customer_history.model import CustomerVisitHistory
from app.accounts.crm.rank_rules.model import CRMBranchRankRule
from app.accounts.crm.loyalty.model import (
    CustomerLoyaltyAccount,
    LoyaltyTransaction,
)


# ============================================================
# CALCULATE CUSTOMER RANK
# ============================================================

async def calculate_customer_rank(
    db,
    customer: Customer | int,
    branch_id: int | None = None,
) -> str | None:
    """
    Calculate customer rank strictly from Customer.total_spend using the active
    CRMBranchRankRule for the customer's branch.

    Rank Thresholds:
      total_spend < silver_min          => Bronze
      silver_min <= total_spend < gold_min => Silver
      total_spend >= gold_min           => Gold

    IMPORTANT: Points redemption NEVER alters total_spend or rank.
    """
    if customer is None:
        return None

    if isinstance(customer, int):
        customer_obj = await db.get(Customer, customer)
        if not customer_obj:
            return None
        customer = customer_obj

    target_branch_id = branch_id if branch_id is not None else customer.branch_id
    if not target_branch_id:
        print("[LOYALTY] Cannot calculate rank: customer has no branch_id")
        return customer.current_rank

    result = await db.execute(
        select(CRMBranchRankRule)
        .where(
            CRMBranchRankRule.client_id == customer.client_id,
            CRMBranchRankRule.branch_id == target_branch_id,
            CRMBranchRankRule.is_active.is_(True),
        )
        .order_by(CRMBranchRankRule.id.desc())
    )
    rule = result.scalars().first()

    if not rule:
        print(
            f"[LOYALTY] No active rank rule found for client_id={customer.client_id}, branch_id={target_branch_id}"
        )
        return customer.current_rank

    total_spend = float(customer.total_spend or 0.0)
    silver_min = float(rule.silver_min or 0.0)
    gold_min = float(rule.gold_min or 0.0)

    if total_spend >= gold_min:
        new_rank = "Gold"
    elif total_spend >= silver_min:
        new_rank = "Silver"
    else:
        new_rank = "Bronze"

    customer.current_rank = new_rank

    # Sync loyalty account balance to customer model without altering balances
    account_result = await db.execute(
        select(CustomerLoyaltyAccount).where(
            CustomerLoyaltyAccount.customer_id == customer.id
        )
    )
    loyalty_account = account_result.scalar_one_or_none()

    if not loyalty_account:
        loyalty_account = CustomerLoyaltyAccount(
            customer_id=customer.id,
            client_id=customer.client_id,
            total_points_earned=0.0,
            total_points_redeemed=0.0,
            current_points_balance=0.0,
            converted_spend=0.0,
        )
        db.add(loyalty_account)
        customer.loyalty_points = 0.0
    else:
        customer.loyalty_points = float(loyalty_account.current_points_balance or 0.0)

    await db.flush()
    return new_rank


# ============================================================
# UPDATE CUSTOMER AFTER ORDER
# ============================================================

async def update_customer_after_order(
    db,
    customer: Customer,
    order,
) -> str | None:
    """
    Update customer CRM statistics after an order.
    """
    if customer is None:
        return None

    order_amount = float(order.total_amount or 0.0)

    old_total_spend = float(customer.total_spend or 0.0)
    new_total_spend = round(old_total_spend + order_amount, 2)

    customer.total_spend = new_total_spend
    customer.current_spend = round(float(customer.current_spend or 0.0) + order_amount, 2)

    customer.total_orders = int(customer.total_orders or 0) + 1
    customer.total_visits = int(customer.total_visits or 0) + 1

    customer.last_order_amount = order_amount
    customer.last_order_id = order.id

    if not customer.first_visit_at:
        customer.first_visit_at = order.created_at or datetime.utcnow()

    customer.last_visit_at = order.created_at or datetime.utcnow()

    if customer.total_orders > 0:
        customer.average_order_value = round(customer.total_spend / customer.total_orders, 2)

    new_rank = await calculate_customer_rank(
        db=db,
        customer=customer,
        branch_id=order.branch_id,
    )

    await db.flush()
    return new_rank


# ============================================================
# RECALCULATE CUSTOMER CRM
# ============================================================

async def recalculate_customer_crm(
    db,
    customer_id: int,
    branch_id: int | None = None,
) -> Customer | None:
    customer = await db.get(Customer, customer_id)
    if not customer:
        return None

    from app.accounts.order.model import Order

    stmt = (
        select(CustomerVisitHistory)
        .outerjoin(Order, CustomerVisitHistory.order_id == Order.id)
        .where(
            CustomerVisitHistory.customer_id == customer_id,
            or_(
                CustomerVisitHistory.order_id.is_(None),
                func.lower(Order.status) != "cancelled",
            ),
        )
        .order_by(CustomerVisitHistory.visit_date.asc())
    )

    result = await db.execute(stmt)
    visits = result.scalars().all()

    total_visits = len(visits)
    total_spend = round(
        sum(float(visit.total_amount or 0.0) for visit in visits),
        2,
    )

    if total_visits == 0 and customer.total_spend:
        total_spend = float(customer.total_spend)

    customer.total_visits = total_visits
    customer.total_orders = total_visits
    customer.total_spend = total_spend

    if total_visits > 0:
        customer.average_order_value = round(total_spend / total_visits, 2)
        last_visit = visits[-1]
        customer.last_visit_at = last_visit.visit_date
        customer.last_order_amount = float(last_visit.total_amount or 0.0)
        if last_visit.order_id:
            customer.last_order_id = last_visit.order_id
        if visits[0].visit_date:
            customer.first_visit_at = visits[0].visit_date

    target_branch_id = branch_id or customer.branch_id
    await calculate_customer_rank(
        db=db,
        customer=customer,
        branch_id=target_branch_id,
    )

    await db.flush()
    return customer


# ============================================================
# GET / CREATE LOYALTY ACCOUNT
# ============================================================

async def get_loyalty_account(
    db,
    customer_id: int,
    lock: bool = False,
) -> CustomerLoyaltyAccount | None:
    stmt = select(CustomerLoyaltyAccount).where(
        CustomerLoyaltyAccount.customer_id == customer_id
    )
    if lock:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        customer = await db.get(Customer, customer_id)
        if not customer:
            return None

        account = CustomerLoyaltyAccount(
            customer_id=customer.id,
            client_id=customer.client_id,
            total_points_earned=float(customer.loyalty_points or 0.0),
            total_points_redeemed=0.0,
            current_points_balance=float(customer.loyalty_points or 0.0),
            converted_spend=0.0,
        )
        db.add(account)
        await db.flush()

    return account


# ============================================================
# GET LOYALTY TRANSACTIONS
# ============================================================

async def get_loyalty_transactions(
    db,
    customer_id: int,
) -> list[LoyaltyTransaction]:
    result = await db.execute(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.customer_id == customer_id)
        .order_by(LoyaltyTransaction.created_at.desc())
    )
    return result.scalars().all()


# ============================================================
# CONVERT CURRENT SPEND -> LOYALTY POINTS
# ============================================================

async def convert_current_spend_to_loyalty_points(
    db,
    customer_id: int,
):
    """
    Convert accumulated current spend into loyalty points and reset current_spend to 0.0.

    BUSINESS RULES:
    1. Customer.total_spend is lifetime spend and MUST NEVER be reset or reduced.
    2. Rank calculation uses total_spend.
    3. Converts Customer.current_spend to loyalty points.
    4. Creates a LoyaltyTransaction record of type 'REDEEM'.
    5. Resets Customer.current_spend = 0.0 after successful processing.
    """
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if not customer.client_id:
        raise HTTPException(status_code=400, detail="Customer does not have client_id")

    if not customer.branch_id:
        raise HTTPException(status_code=400, detail="Customer does not have branch_id")

    current_spend = round(float(customer.current_spend or 0.0), 2)
    if current_spend <= 0:
        raise HTTPException(
            status_code=400,
            detail="Customer has no current spend available for loyalty conversion",
        )

    history_result = await db.execute(
        select(CustomerVisitHistory)
        .where(CustomerVisitHistory.customer_id == customer_id)
        .order_by(CustomerVisitHistory.visit_date.desc(), CustomerVisitHistory.id.desc())
        .limit(1)
    )
    history = history_result.scalar_one_or_none()

    total_spend = round(float(customer.total_spend or (history.current_spend if history else 0.0) or 0.0), 2)
    if total_spend < 0:
        raise HTTPException(status_code=400, detail="Customer spend cannot be negative")

    rule_result = await db.execute(
        select(CRMBranchRankRule)
        .where(
            CRMBranchRankRule.client_id == customer.client_id,
            CRMBranchRankRule.branch_id == customer.branch_id,
            CRMBranchRankRule.is_active.is_(True),
        )
        .order_by(CRMBranchRankRule.id.desc())
    )
    rule = rule_result.scalars().first()

    if not rule:
        raise HTTPException(
            status_code=404,
            detail=f"Active rank rule not found for client_id={customer.client_id}, branch_id={customer.branch_id}",
        )

    silver_min = float(rule.silver_min or 0.0)
    gold_min = float(rule.gold_min or 0.0)

    # Rank calculation uses lifetime total_spend
    if total_spend >= gold_min:
        rank = "Gold"
        points_per_100 = float(rule.gold_pts or 0.0)
    elif total_spend >= silver_min:
        rank = "Silver"
        points_per_100 = float(rule.silver_pts or 0.0)
    else:
        rank = "Bronze"
        points_per_100 = float(rule.bronze_pts or 0.0)

    customer.current_rank = rank

    loyalty_account = await get_loyalty_account(db, customer_id)

    previously_converted_spend = round(float(loyalty_account.converted_spend or 0.0), 2)

    loyalty_points = round((current_spend / 100.0) * points_per_100, 2)
    if loyalty_points <= 0:
        raise HTTPException(status_code=400, detail="Calculated loyalty points are zero")

    old_earned = float(loyalty_account.total_points_earned or 0.0)
    old_balance = float(loyalty_account.current_points_balance or 0.0)

    new_total_earned = round(old_earned + loyalty_points, 2)
    new_balance = round(old_balance + loyalty_points, 2)
    new_converted_spend = round(previously_converted_spend + current_spend, 2)

    loyalty_account.converted_spend = new_converted_spend
    loyalty_account.total_points_earned = new_total_earned
    loyalty_account.current_points_balance = max(new_balance, 0.0)

    customer.loyalty_points = loyalty_account.current_points_balance

    # Create permanent REDEEM loyalty transaction record
    transaction = LoyaltyTransaction(
        account_id=loyalty_account.id,
        customer_id=customer.id,
        bill_id=history.bill_id if history else None,
        transaction_type="REDEEM",
        points=loyalty_points,
        balance_after=loyalty_account.current_points_balance,
        description=(
            f"Redeemed ₹{current_spend:.2f} current spend for {loyalty_points:g} loyalty points "
            f"({rank} rank rate: {points_per_100:g} points per ₹100)."
        ),
        created_at=datetime.utcnow(),
    )
    db.add(transaction)

    # ONLY after successful processing, reset current_spend to 0.0
    customer.current_spend = 0.0

    await db.flush()

    return {
        "message": "Loyalty points converted successfully",
        "customer_id": customer.id,
        "history_id": history.id if history else None,
        "bill_id": history.bill_id if history else None,
        "current_spend": float(customer.current_spend or 0.0),
        "previously_converted_spend": previously_converted_spend,
        "eligible_spend": current_spend,
        "converted_spend": new_converted_spend,
        "rank": rank,
        "points_per_100": points_per_100,
        "points_earned": loyalty_points,
        "total_points_earned": new_total_earned,
        "total_points_redeemed": float(loyalty_account.total_points_redeemed or 0.0),
        "current_points_balance": loyalty_account.current_points_balance,
    }


# ============================================================
# REDEEM LOYALTY POINTS
# ============================================================

async def redeem_loyalty_points(
    db,
    customer_id: int,
    points_to_redeem: float,
    bill_id: int | None = None,
    description: str | None = None,
) -> dict:
    """
    Redeem loyalty points for a customer.

    BUSINESS RULES:
    1. Points redemption NEVER modifies customer.total_spend.
    2. Points redemption NEVER modifies customer.current_rank.
    3. Points redemption NEVER modifies CustomerVisitHistory.current_spend or customer.current_spend.
    4. Only loyalty_account.total_points_redeemed, loyalty_account.current_points_balance,
       and customer.loyalty_points are updated.
    5. A LoyaltyTransaction record of type 'REDEEM' is created.
    """
    points_to_redeem = round(float(points_to_redeem or 0.0), 2)
    if points_to_redeem <= 0:
        raise HTTPException(
            status_code=400,
            detail="Points to redeem must be greater than 0",
        )

    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    loyalty_account = await get_loyalty_account(db, customer_id)
    if not loyalty_account:
        raise HTTPException(
            status_code=404,
            detail="Customer loyalty account not found",
        )

    current_balance = float(loyalty_account.current_points_balance or 0.0)
    if current_balance < points_to_redeem:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient loyalty points. Current balance: {current_balance}, requested: {points_to_redeem}",
        )

    # Update account balances
    new_redeemed = round(float(loyalty_account.total_points_redeemed or 0.0) + points_to_redeem, 2)
    new_balance = round(current_balance - points_to_redeem, 2)

    loyalty_account.total_points_redeemed = new_redeemed
    loyalty_account.current_points_balance = max(new_balance, 0.0)

    # Sync on customer object (points balance AND reset redemption-cycle current_spend)
    # (Note: total_spend, current_rank, total_visits, total_orders, and history rows remain unchanged)
    customer.loyalty_points = loyalty_account.current_points_balance
    customer.current_spend = 0.0

    # Create transaction log
    desc = description or f"Redeemed {points_to_redeem} loyalty points"
    transaction = LoyaltyTransaction(
        account_id=loyalty_account.id,
        customer_id=customer.id,
        bill_id=bill_id,
        transaction_type="REDEEM",
        points=points_to_redeem,
        balance_after=loyalty_account.current_points_balance,
        description=desc,
        created_at=datetime.utcnow(),
    )
    db.add(transaction)

    await db.flush()

    return {
        "message": "Loyalty points redeemed successfully",
        "customer_id": customer.id,
        "points_redeemed": points_to_redeem,
        "total_points_redeemed": loyalty_account.total_points_redeemed,
        "current_points_balance": loyalty_account.current_points_balance,
        "current_rank": customer.current_rank,
        "total_spend": float(customer.total_spend or 0.0),
        "current_spend": float(customer.current_spend or 0.0),
    }