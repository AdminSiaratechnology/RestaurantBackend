"""
app/accounts/crm/rank_rules/service.py

Business Logic Service Layer for CRM Branch Rank Rules.
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.branch.model import Branch
from app.accounts.customer.model import Customer
from app.accounts.crm.rank_rules.model import CRMBranchRankRule
from app.accounts.crm.rank_rules.repository import RankRuleRepository
from app.accounts.crm.rank_rules.schema import (
    PaginationResponse,
    RankRuleBase,
    RankRuleCreate,
    RankRuleListResponse,
    RankRuleResponse,
    RankRuleUpdate,
)
from app.accounts.crm.utils.logger import crm_logger
from app.accounts.enum import UserRole


# ============================================================
# CLIENT ID
# ============================================================

def _extract_client_id(current_user) -> int:

    if isinstance(current_user, dict):

        role = current_user.get("role")
        user = current_user.get("user")

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authentication context.",
            )

        if role == UserRole.CLIENT:

            client_id = getattr(
                user,
                "id",
                None,
            )

            if client_id is not None:
                return int(client_id)

        elif role == UserRole.STAFF:

            client_id = getattr(
                user,
                "client_id",
                None,
            )

            if client_id is not None:
                return int(client_id)

        elif role in (
            UserRole.SUPER_ADMIN,
            UserRole.PARTNER,
        ):

            client_id = getattr(
                user,
                "client_id",
                None,
            )

            if client_id is None:
                client_id = getattr(
                    user,
                    "id",
                    None,
                )

            if client_id is not None:
                return int(client_id)

    client_id = getattr(
        current_user,
        "client_id",
        None,
    )

    if client_id is not None:
        return int(client_id)

    client_id = getattr(
        current_user,
        "id",
        None,
    )

    if client_id is not None:
        return int(client_id)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Unable to determine client.",
    )


# ============================================================
# CREATE
# ============================================================

async def create_rank_rule_service(
    db: AsyncSession,
    current_user,
    payload: RankRuleCreate,
) -> RankRuleResponse:

    repo = RankRuleRepository(db)

    client_id = _extract_client_id(
        current_user
    )

    branch = await db.get(
        Branch,
        payload.branch_id,
    )

    if not branch:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found.",
        )

    if branch.client_id != client_id:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this branch.",
        )

    if await repo.rule_exists(
        client_id=client_id,
        branch_id=payload.branch_id,
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"An active rank rule already exists "
                f"for Branch #{payload.branch_id}."
            ),
        )

    try:

        rule = await repo.create_rule(
            client_id=client_id,
            branch_id=payload.branch_id,
            bronze_max=payload.bronze_max,
            silver_min=payload.silver_min,
            silver_max=payload.silver_max,
            gold_min=payload.gold_min,
            bronze_pts=payload.bronze_pts,
            silver_pts=payload.silver_pts,
            gold_pts=payload.gold_pts,
        )

    except Exception as exc:

        await db.rollback()

        crm_logger.error(
            f"[RankRules] Failed to create rule: {exc}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rank rule.",
        )

    crm_logger.info(
        f"[RankRules] Created rank rule "
        f"for Branch #{payload.branch_id} "
        f"(Client #{client_id})"
    )

    return RankRuleResponse.model_validate(rule)


# ============================================================
# GET
# ============================================================

async def get_rank_rule_service(
    db: AsyncSession,
    current_user,
    branch_id: int,
) -> RankRuleResponse:

    repo = RankRuleRepository(db)

    client_id = _extract_client_id(
        current_user
    )

    rule = await repo.get_branch_rule(
        client_id=client_id,
        branch_id=branch_id,
        is_active_only=True,
    )

    if not rule:
        return RankRuleResponse(
            id=0,
            client_id=client_id,
            branch_id=branch_id,
            bronze_min=0.0,
            bronze_max=15000.0,
            silver_min=15000.0,
            silver_max=35000.0,
            gold_min=35000.0,
            bronze_pts=1.0,
            silver_pts=2.0,
            gold_pts=3.0,
            is_active=True,
        )

    return RankRuleResponse.model_validate(rule)


# ============================================================
# UPDATE
# ============================================================

async def update_rank_rule_service(
    db: AsyncSession,
    current_user,
    branch_id: int,
    payload: RankRuleUpdate,
) -> RankRuleResponse:

    repo = RankRuleRepository(db)

    client_id = _extract_client_id(
        current_user
    )

    rule = await repo.get_branch_rule(
        client_id=client_id,
        branch_id=branch_id,
        is_active_only=True,
    )

    if not rule:
        b_max = payload.bronze_max if payload.bronze_max is not None else 15000.0
        s_min = payload.silver_min if payload.silver_min is not None else b_max
        s_max = payload.silver_max if payload.silver_max is not None else 35000.0
        g_min = payload.gold_min if payload.gold_min is not None else s_max
        b_pts = payload.bronze_pts if payload.bronze_pts is not None else 1.0
        s_pts = payload.silver_pts if payload.silver_pts is not None else 2.0
        g_pts = payload.gold_pts if payload.gold_pts is not None else 3.0

        created = await repo.create_rule(
            client_id=client_id,
            branch_id=branch_id,
            bronze_max=b_max,
            silver_min=s_min,
            silver_max=s_max,
            gold_min=g_min,
            bronze_pts=b_pts,
            silver_pts=s_pts,
            gold_pts=g_pts,
        )
        return RankRuleResponse.model_validate(created)

    update_data = payload.model_dump(
        exclude_unset=True
    )

    # branch_id cannot be changed here
    update_data.pop(
        "branch_id",
        None,
    )

    if not update_data:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    # ========================================================
    # BRONZE MIN
    # ========================================================

    if "bronze_min" in update_data:

        if update_data["bronze_min"] != 0:

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="bronze_min must be 0.",
            )

        update_data.pop(
            "bronze_min",
            None,
        )

    # ========================================================
    # FINAL VALUES
    # ========================================================

    final_values = {
        "bronze_min": 0.0,

        "bronze_max": update_data.get(
            "bronze_max",
            rule.bronze_max,
        ),

        "silver_min": update_data.get(
            "silver_min",
            rule.silver_min,
        ),

        "silver_max": update_data.get(
            "silver_max",
            rule.silver_max,
        ),

        "gold_min": update_data.get(
            "gold_min",
            rule.gold_min,
        ),

        "bronze_pts": update_data.get(
            "bronze_pts",
            rule.bronze_pts,
        ),

        "silver_pts": update_data.get(
            "silver_pts",
            rule.silver_pts,
        ),

        "gold_pts": update_data.get(
            "gold_pts",
            rule.gold_pts,
        ),
    }

    # ========================================================
    # VALIDATE
    # ========================================================

    try:

        RankRuleBase(
            **final_values
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # ========================================================
    # UPDATE
    # ========================================================

    try:

        updated = await repo.update_rule(
            rule=rule,
            update_data=update_data,
        )

    except Exception as exc:

        await db.rollback()

        crm_logger.error(
            f"[RankRules] Failed to update rule: {exc}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update rank rule.",
        )

    return RankRuleResponse.model_validate(
        updated
    )


# ============================================================
# DELETE
# ============================================================

async def delete_rank_rule_service(
    db: AsyncSession,
    current_user,
    branch_id: int,
) -> RankRuleResponse:

    repo = RankRuleRepository(db)

    client_id = _extract_client_id(
        current_user
    )

    rule = await repo.get_branch_rule(
        client_id=client_id,
        branch_id=branch_id,
        is_active_only=True,
    )

    if not rule:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Active rank rule not found "
                f"for Branch #{branch_id}."
            ),
        )

    deleted = await repo.delete_rule(
        rule
    )

    return RankRuleResponse.model_validate(
        deleted
    )


# ============================================================
# LIST
# ============================================================

async def list_rank_rules_service(
    db: AsyncSession,
    current_user,
    branch_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
) -> RankRuleListResponse:

    repo = RankRuleRepository(db)

    client_id = _extract_client_id(
        current_user
    )

    # ========================================================
    # SPECIFIC BRANCH VALIDATION
    #
    # None means ALL branches.
    # ========================================================

    if branch_id is not None:

        branch = await db.get(
            Branch,
            branch_id,
        )

        if not branch:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branch not found.",
            )

        if branch.client_id != client_id:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You are not allowed to access "
                    "this branch."
                ),
            )

    items, total, total_pages = await repo.list_rules(
        client_id=client_id,
        branch_id=branch_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return RankRuleListResponse(
        items=[
            RankRuleResponse.model_validate(item)
            for item in items
        ],
        pagination=PaginationResponse(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


# ============================================================
# CALCULATE RANK
# ============================================================

def calculate_customer_rank(
    total_spend: float,
    rule: CRMBranchRankRule,
) -> str:

    total_spend = float(
        total_spend or 0
    )

    if total_spend >= float(
        rule.gold_min
    ):
        return "Gold"

    if total_spend >= float(
        rule.silver_min
    ):
        return "Silver"

    return "Bronze"


# ============================================================
# POINT RATE
# ============================================================

def get_points_rate_for_rank(
    rank: str,
    rule: CRMBranchRankRule,
) -> float:

    rank = str(
        rank or ""
    ).lower()

    if rank == "gold":

        return float(
            rule.gold_pts or 0
        )

    if rank == "silver":

        return float(
            rule.silver_pts or 0
        )

    return float(
        rule.bronze_pts or 0
    )


# ============================================================
# TRANSACTION POINTS
# ============================================================

def calculate_transaction_points(
    transaction_amount: float,
    points_per_100: float,
) -> float:

    transaction_amount = float(
        transaction_amount or 0
    )

    points_per_100 = float(
        points_per_100 or 0
    )

    if transaction_amount <= 0:
        return 0.0

    return round(
        (
            transaction_amount / 100.0
        )
        * points_per_100,
        2,
    )


# ============================================================
# GET CUSTOMER RANK
# ============================================================

async def get_customer_rank_service(
    db: AsyncSession,
    client_id: int,
    branch_id: int,
    total_spend: float,
) -> dict:

    repo = RankRuleRepository(db)

    rule = await repo.get_branch_rule(
        client_id=client_id,
        branch_id=branch_id,
        is_active_only=True,
    )

    if not rule:

        return {
            "rank": "Bronze",
            "points_per_100": 0.0,
            "has_rule": False,
            "rule_id": None,
        }

    rank = calculate_customer_rank(
        total_spend=total_spend,
        rule=rule,
    )

    points_per_100 = get_points_rate_for_rank(
        rank=rank,
        rule=rule,
    )

    return {
        "rank": rank,
        "points_per_100": points_per_100,
        "has_rule": True,
        "rule_id": rule.id,
    }


# ============================================================
# CALCULATE LOYALTY FOR TRANSACTION
# ============================================================

async def calculate_loyalty_for_transaction(
    db: AsyncSession,
    client_id: int,
    branch_id: int,
    current_total_spend: float,
    transaction_amount: float,
) -> dict:

    current_total_spend = float(
        current_total_spend or 0
    )

    transaction_amount = float(
        transaction_amount or 0
    )

    if transaction_amount <= 0:

        return {
            "old_rank": "Bronze",
            "points_per_100": 0.0,
            "transaction_amount": 0.0,
            "earned_points": 0.0,
            "old_total_spend": current_total_spend,
            "new_total_spend": current_total_spend,
            "new_rank": "Bronze",
            "has_rule": False,
            "rule_id": None,
        }

    # ========================================================
    # OLD RANK
    # ========================================================

    rank_data = await get_customer_rank_service(
        db=db,
        client_id=client_id,
        branch_id=branch_id,
        total_spend=current_total_spend,
    )

    old_rank = rank_data["rank"]

    points_per_100 = rank_data[
        "points_per_100"
    ]

    # ========================================================
    # EARN POINTS USING OLD RANK
    # ========================================================

    earned_points = calculate_transaction_points(
        transaction_amount=transaction_amount,
        points_per_100=points_per_100,
    )

    # ========================================================
    # NEW LIFETIME SPEND
    # ========================================================

    new_total_spend = round(
        current_total_spend
        + transaction_amount,
        2,
    )

    # ========================================================
    # NEW RANK
    # ========================================================

    new_rank_data = await get_customer_rank_service(
        db=db,
        client_id=client_id,
        branch_id=branch_id,
        total_spend=new_total_spend,
    )

    new_rank = new_rank_data["rank"]

    return {
        "old_rank": old_rank,
        "points_per_100": points_per_100,
        "transaction_amount": transaction_amount,
        "earned_points": earned_points,
        "old_total_spend": current_total_spend,
        "new_total_spend": new_total_spend,
        "new_rank": new_rank,
        "has_rule": rank_data["has_rule"],
        "rule_id": rank_data["rule_id"],
    }


# ============================================================
# UPDATE CUSTOMER LOYALTY AFTER PURCHASE
# ============================================================

async def update_customer_loyalty(
    db: AsyncSession,
    customer_id: int,
    client_id: int,
    branch_id: int,
    transaction_amount: float,
) -> dict:

    transaction_amount = float(
        transaction_amount or 0
    )

    if transaction_amount <= 0:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Transaction amount must be "
                "greater than 0."
            ),
        )

    # ========================================================
    # CUSTOMER
    # ========================================================

    customer = await db.get(
        Customer,
        customer_id,
    )

    if not customer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    # ========================================================
    # SECURITY
    # ========================================================

    if customer.client_id != client_id:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Customer does not belong "
                "to this client."
            ),
        )

    # ========================================================
    # CURRENT LIFETIME SPEND
    # ========================================================

    current_total_spend = float(
        customer.total_spend or 0
    )

    # ========================================================
    # CURRENT SPEND
    # ========================================================

    current_spend = float(
        customer.current_spend or 0
    )

    # ========================================================
    # CURRENT POINTS
    # ========================================================

    current_points = float(
        customer.loyalty_points or 0
    )

    # ========================================================
    # CALCULATE LOYALTY
    # ========================================================

    loyalty = await calculate_loyalty_for_transaction(
        db=db,
        client_id=client_id,
        branch_id=branch_id,
        current_total_spend=current_total_spend,
        transaction_amount=transaction_amount,
    )

    earned_points = float(
        loyalty["earned_points"]
    )

    new_total_spend = float(
        loyalty["new_total_spend"]
    )

    new_rank = loyalty["new_rank"]

    # ========================================================
    # UPDATE LIFETIME SPEND
    # ========================================================

    customer.total_spend = round(
        new_total_spend,
        2,
    )

    # ========================================================
    # UPDATE CURRENT SPEND
    #
    # PURCHASE -> ADD
    # ========================================================

    customer.current_spend = round(
        current_spend
        + transaction_amount,
        2,
    )

    # ========================================================
    # UPDATE POINTS
    # ========================================================

    customer.loyalty_points = round(
        current_points
        + earned_points,
        2,
    )

    # ========================================================
    # UPDATE RANK
    # ========================================================

    customer.current_rank = new_rank

    # ========================================================
    # UPDATE LAST ORDER AMOUNT
    # ========================================================

    customer.last_order_amount = round(
        transaction_amount,
        2,
    )

    # ========================================================
    # COMMIT
    # ========================================================

    try:

        await db.commit()

        await db.refresh(customer)

    except Exception as exc:

        await db.rollback()

        crm_logger.error(
            f"[CRM Loyalty] Failed to update "
            f"Customer #{customer_id}: {exc}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update customer loyalty.",
        )

    # ========================================================
    # LOG
    # ========================================================

    crm_logger.info(
        f"[CRM Loyalty] Customer #{customer_id} | "
        f"Branch #{branch_id} | "
        f"Lifetime Spend "
        f"{current_total_spend:.2f} -> "
        f"{float(customer.total_spend):.2f} | "
        f"Current Spend "
        f"{current_spend:.2f} -> "
        f"{float(customer.current_spend):.2f} | "
        f"Points "
        f"{current_points:.2f} -> "
        f"{float(customer.loyalty_points):.2f} | "
        f"Rank "
        f"{loyalty['old_rank']} -> "
        f"{new_rank} | "
        f"Earned "
        f"{earned_points:.2f}"
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "customer_id": customer.id,
        "branch_id": branch_id,

        "old_rank": loyalty["old_rank"],
        "new_rank": new_rank,

        "old_total_spend": current_total_spend,
        "new_total_spend": float(
            customer.total_spend
        ),

        "old_current_spend": current_spend,
        "new_current_spend": float(
            customer.current_spend
        ),

        "old_points": current_points,
        "earned_points": earned_points,
        "total_points": float(
            customer.loyalty_points
        ),

        "points_per_100": loyalty[
            "points_per_100"
        ],

        "transaction_amount": transaction_amount,

        "redeem_count": int(
            customer.redeem_count or 0
        ),

        "has_rule": loyalty["has_rule"],
        "rule_id": loyalty["rule_id"],
    }


# ============================================================
# REDEEM CURRENT SPEND
# ============================================================

async def redeem_current_spend(
    db: AsyncSession,
    customer_id: int,
    client_id: int,
    redeem_amount: float,
) -> dict:

    redeem_amount = float(
        redeem_amount or 0
    )

    if redeem_amount <= 0:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Redeem amount must be "
                "greater than 0."
            ),
        )

    # ========================================================
    # GET CUSTOMER
    # ========================================================

    customer = await db.get(
        Customer,
        customer_id,
    )

    if not customer:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    # ========================================================
    # SECURITY
    # ========================================================

    if customer.client_id != client_id:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Customer does not belong "
                "to this client."
            ),
        )

    # ========================================================
    # CURRENT SPEND
    # ========================================================

    old_current_spend = float(
        customer.current_spend or 0
    )

    # ========================================================
    # VALIDATE REDEEM AMOUNT
    # ========================================================

    if redeem_amount > old_current_spend:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Redeem amount ₹{redeem_amount:.2f} "
                f"cannot be greater than current spend "
                f"₹{old_current_spend:.2f}."
            ),
        )

    # ========================================================
    # NEW CURRENT SPEND
    # ========================================================

    new_current_spend = round(
        old_current_spend
        - redeem_amount,
        2,
    )

    # Prevent tiny floating point negative value.
    if new_current_spend < 0:
        new_current_spend = 0.0

    # ========================================================
    # UPDATE CURRENT SPEND
    # ========================================================

    customer.current_spend = new_current_spend

    # ========================================================
    # INCREMENT REDEEM COUNT
    #
    # THIS IS THE IMPORTANT FIX.
    # ========================================================

    old_redeem_count = int(
        customer.redeem_count or 0
    )

    customer.redeem_count = (
        old_redeem_count + 1
    )

    # ========================================================
    # IMPORTANT
    #
    # DO NOT MODIFY:
    #
    # customer.total_spend
    # customer.current_rank
    #
    # Redemption does not affect lifetime spend
    # or rank.
    # ========================================================

    try:

        await db.commit()

        await db.refresh(customer)

    except Exception as exc:

        await db.rollback()

        crm_logger.error(
            f"[CRM Loyalty] Redemption failed "
            f"for Customer #{customer_id}: {exc}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to redeem current spend.",
        )

    # ========================================================
    # LOG
    # ========================================================

    crm_logger.info(
        f"[CRM Loyalty] Redemption | "
        f"Customer #{customer_id} | "
        f"Redeemed ₹{redeem_amount:.2f} | "
        f"Current Spend "
        f"{old_current_spend:.2f} -> "
        f"{new_current_spend:.2f} | "
        f"Redeem Count "
        f"{old_redeem_count} -> "
        f"{customer.redeem_count}"
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "customer_id": customer.id,

        "redeemed_amount": redeem_amount,

        "old_current_spend": old_current_spend,

        "current_spend": float(
            customer.current_spend
        ),

        "total_spend": float(
            customer.total_spend or 0
        ),

        "redeem_count": int(
            customer.redeem_count or 0
        ),

        "current_rank": customer.current_rank,

        "loyalty_points": float(
            customer.loyalty_points or 0
        ),
    }