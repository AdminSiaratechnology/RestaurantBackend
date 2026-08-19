"""
CRM Wallet Service.

Responsibilities:
- Customer wallet account management
- Wallet transactions
- Loyalty points -> wallet conversion
- Wallet discount calculation
- Wallet debit

Important:
Wallet is NOT a payment method.
It is only used as a discount/contribution against a bill.
"""

from fastapi import HTTPException
from sqlalchemy import select

from app.accounts.branch.model import Branch, statusEnum
from app.accounts.customer.model import Customer
from app.accounts.crm.loyalty.model import (
    CustomerLoyaltyAccount,
    LoyaltyTransaction,
)
from app.accounts.crm.loyalty.conversion_rule.model import (
    LoyaltyConversionRule,
)
from app.accounts.crm.wallet.model import (
    CustomerWalletAccount,
    WalletTransaction,
)


# ============================================================
# GET CUSTOMER
# ============================================================


async def get_customer(
    db,
    customer_id: int,
):
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id
        )
    )

    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="CRM customer not found",
        )

    return customer


# ============================================================
# GET BRANCH
# ============================================================


async def get_branch(
    db,
    branch_id: int,
    client_id: int,
):
    """
    Get and validate branch.

    Branch must:
    - exist
    - belong to client
    - be active
    """

    result = await db.execute(
        select(Branch).where(
            Branch.id == branch_id,
            Branch.client_id == client_id,
        )
    )

    branch = result.scalar_one_or_none()

    if branch is None:
        raise HTTPException(
            status_code=404,
            detail="Branch not found for this client",
        )

    # Handle SQLAlchemy enum safely.
    branch_status = branch.status

    if hasattr(branch_status, "value"):
        branch_status = branch_status.value

    if str(branch_status).lower() != "active":
        raise HTTPException(
            status_code=400,
            detail="Branch is inactive",
        )

    return branch


# ============================================================
# GET LOYALTY ACCOUNT
# ============================================================


async def get_loyalty_account(
    db,
    customer_id: int,
):
    result = await db.execute(
        select(CustomerLoyaltyAccount)
        .where(
            CustomerLoyaltyAccount.customer_id
            == customer_id
        )
        .with_for_update()
    )

    return result.scalar_one_or_none()


# ============================================================
# GET / CREATE WALLET
# ============================================================


async def get_or_create_wallet_account(
    db,
    customer_id: int,
    client_id: int,
    lock: bool = False,
):
    """
    Get customer's wallet.

    If wallet doesn't exist, create it
    with zero balance.

    Wallet is NOT a payment method.
    """

    query = (
        select(CustomerWalletAccount)
        .where(
            CustomerWalletAccount.customer_id
            == customer_id,
            CustomerWalletAccount.client_id
            == client_id,
        )
    )

    if lock:
        query = query.with_for_update()

    result = await db.execute(query)

    wallet = result.scalar_one_or_none()

    if wallet is not None:
        return wallet

    wallet = CustomerWalletAccount(
        customer_id=customer_id,
        client_id=client_id,
        balance=0.0,
        total_recharged=0.0,
        total_spent=0.0,
        is_active=True,
    )

    db.add(wallet)

    await db.flush()

    return wallet


# ============================================================
# GET WALLET
# ============================================================


async def get_wallet_account(
    db,
    customer_id: int,
    client_id: int | None = None,
    lock: bool = False,
):
    conditions = [
        CustomerWalletAccount.customer_id
        == customer_id
    ]

    if client_id is not None:
        conditions.append(
            CustomerWalletAccount.client_id
            == client_id
        )

    query = (
        select(CustomerWalletAccount)
        .where(*conditions)
    )

    if lock:
        query = query.with_for_update()

    result = await db.execute(query)

    return result.scalar_one_or_none()


# ============================================================
# GET WALLET TRANSACTIONS
# ============================================================


async def get_wallet_transactions(
    db,
    customer_id: int,
    client_id: int | None = None,
):
    conditions = [
        WalletTransaction.customer_id
        == customer_id
    ]

    if client_id is not None:
        conditions.append(
            WalletTransaction.client_id
            == client_id
        )

    result = await db.execute(
        select(WalletTransaction)
        .where(*conditions)
        .order_by(
            WalletTransaction.created_at.desc()
        )
    )

    return result.scalars().all()


# ============================================================
# GET LOYALTY CONVERSION RULE
# ============================================================


async def get_loyalty_conversion_rule(
    db,
    client_id: int,
    branch_id: int,
):
    """
    Get active loyalty conversion rule.

    IMPORTANT:
    Do not depend only on SQLAlchemy `.is_(True)` here.
    Some existing databases may contain boolean-like
    values differently.

    We first filter by client + branch and then validate
    is_active in Python.
    """

    result = await db.execute(
        select(LoyaltyConversionRule)
        .where(
            LoyaltyConversionRule.client_id
            == client_id,
            LoyaltyConversionRule.branch_id
            == branch_id,
        )
        .order_by(
            LoyaltyConversionRule.id.desc()
        )
    )

    rules = result.scalars().all()

    for rule in rules:

        is_active = rule.is_active

        # Boolean
        if is_active is True:
            return rule

        # Enum
        if hasattr(is_active, "value"):
            is_active = is_active.value

        # String values
        if str(is_active).strip().lower() in {
            "true",
            "1",
            "active",
            "yes",
        }:
            return rule

    return None


# ============================================================
# VALIDATE CONVERSION RULE
# ============================================================


def validate_conversion_rule(rule):

    if rule is None:
        raise ValueError(
            "No active loyalty conversion rule found "
            "for this branch"
        )

    if rule.points_required is None:
        raise ValueError(
            "Invalid loyalty conversion rule: "
            "points_required is missing"
        )

    if rule.rupee_value is None:
        raise ValueError(
            "Invalid loyalty conversion rule: "
            "rupee_value is missing"
        )

    if float(rule.points_required) <= 0:
        raise ValueError(
            "Invalid loyalty conversion rule: "
            "points_required must be greater than 0"
        )

    if float(rule.rupee_value) <= 0:
        raise ValueError(
            "Invalid loyalty conversion rule: "
            "rupee_value must be greater than 0"
        )

    is_active = rule.is_active

    if hasattr(is_active, "value"):
        is_active = is_active.value

    if str(is_active).strip().lower() not in {
        "true",
        "1",
        "active",
        "yes",
    }:
        raise ValueError(
            "Invalid loyalty conversion rule: "
            "rule is inactive"
        )


# ============================================================
# CONVERT LOYALTY -> WALLET
# ============================================================


async def convert_loyalty_points_to_wallet(
    db,
    customer_id: int,
    branch_id: int,
):
    """
    Convert ALL available loyalty points into wallet balance.

    Example:

        Points = 100
        Rule = 10 points = ₹3

        Wallet credit =
            (100 / 10) * 3
            = ₹30

    After successful conversion:

        Loyalty points = 0
        Wallet balance += ₹30
    """

    try:

        # ====================================================
        # 1. GET CUSTOMER
        # ====================================================

        customer = await get_customer(
            db,
            customer_id,
        )

        client_id = customer.client_id

        if client_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Customer is not associated "
                    "with a client"
                ),
            )

        # ====================================================
        # 2. VALIDATE BRANCH
        # ====================================================

        branch = await get_branch(
            db,
            branch_id=branch_id,
            client_id=client_id,
        )

        # ====================================================
        # 3. GET LOYALTY ACCOUNT
        # ====================================================

        loyalty_account = await get_loyalty_account(
            db,
            customer_id,
        )

        if loyalty_account is None:
            raise ValueError(
                "Customer loyalty account not found"
            )

        # ====================================================
        # 4. GET CURRENT POINTS
        # ====================================================

        current_points = round(
            max(
                float(
                    loyalty_account.current_points_balance
                    or 0
                ),
                0.0,
            ),
            2,
        )

        if current_points <= 0:
            raise ValueError(
                "No loyalty points available for conversion"
            )

        # ====================================================
        # 5. GET CONVERSION RULE
        # ====================================================

        rule = await get_loyalty_conversion_rule(
            db,
            client_id=client_id,
            branch_id=branch.id,
        )

        validate_conversion_rule(rule)

        points_required = float(
            rule.points_required
        )

        rupee_value = float(
            rule.rupee_value
        )

        # ====================================================
        # 6. CALCULATE CONVERSION
        # ====================================================

        points_converted = round(
            current_points,
            2,
        )

        rupee_amount = round(
            (
                points_converted
                / points_required
            )
            * rupee_value,
            2,
        )

        if rupee_amount <= 0:
            raise ValueError(
                "Calculated wallet amount is zero"
            )

        # ====================================================
        # 7. GET / CREATE WALLET
        # ====================================================

        wallet = await get_or_create_wallet_account(
            db,
            customer_id=customer_id,
            client_id=client_id,
            lock=True,
        )

        if not wallet.is_active:
            raise ValueError(
                "Customer wallet is inactive"
            )

        # ====================================================
        # 8. WALLET BALANCE
        # ====================================================

        wallet_balance_before = round(
            max(
                float(wallet.balance or 0),
                0.0,
            ),
            2,
        )

        wallet_balance_after = round(
            wallet_balance_before
            + rupee_amount,
            2,
        )

        # ====================================================
        # 9. UPDATE LOYALTY
        # ====================================================

        loyalty_balance_after = 0.0

        loyalty_account.current_points_balance = (
            loyalty_balance_after
        )

        # Keep customer's cached loyalty points in sync.
        if hasattr(customer, "loyalty_points"):
            customer.loyalty_points = (
                loyalty_balance_after
            )

        loyalty_account.total_points_redeemed = round(
            float(
                loyalty_account.total_points_redeemed
                or 0
            )
            + points_converted,
            2,
        )

        # ====================================================
        # 10. UPDATE WALLET
        # ====================================================

        wallet.balance = wallet_balance_after

        # ====================================================
        # 11. LOYALTY TRANSACTION
        # ====================================================

        loyalty_transaction = LoyaltyTransaction(
            account_id=loyalty_account.id,
            customer_id=customer_id,
            transaction_type="CONVERSION",
            points=-points_converted,
            balance_after=loyalty_balance_after,
            description=(
                f"Converted {points_converted:g} "
                f"loyalty points into "
                f"₹{rupee_amount:.2f} wallet balance"
            ),
        )

        db.add(loyalty_transaction)

        await db.flush()

        # ====================================================
        # 12. WALLET TRANSACTION
        # ====================================================

        wallet_transaction = WalletTransaction(
            customer_id=customer_id,
            wallet_account_id=wallet.id,
            client_id=client_id,
            branch_id=branch.id,
            transaction_type="CREDIT",
            amount=rupee_amount,
            balance_before=wallet_balance_before,
            balance_after=wallet_balance_after,
            reference_type="LOYALTY_CONVERSION",
            reference_id=loyalty_transaction.id,
            notes=(
                f"{points_converted:g} loyalty points "
                f"converted to "
                f"₹{rupee_amount:.2f}"
            ),
        )

        db.add(wallet_transaction)

        # ====================================================
        # 13. COMMIT
        # ====================================================

        await db.commit()

        # ====================================================
        # 14. RETURN
        # ====================================================

        return {
            "customer_id": customer_id,
            "points_converted": points_converted,
            "rupee_amount": rupee_amount,
            "conversion_rate_points": points_required,
            "conversion_rate_rupees": rupee_value,
            "loyalty_points_after": loyalty_balance_after,
            "wallet_balance_after": wallet_balance_after,
            "message": (
                f"{points_converted:g} loyalty points "
                f"converted into ₹{rupee_amount:.2f} "
                f"wallet balance successfully"
            ),
        }

    except HTTPException:
        await db.rollback()
        raise

    except ValueError:
        await db.rollback()
        raise

    except Exception as exc:
        await db.rollback()

        print(
            "LOYALTY TO WALLET ERROR:",
            repr(exc),
        )

        raise


# ============================================================
# GET WALLET DISCOUNT RULE
# ============================================================


async def get_wallet_discount_rule(
    db,
    client_id: int,
    branch_id: int,
):
    from app.accounts.crm.loyalty.wallet_discount_rule.model import (
        WalletDiscountRule,
    )

    result = await db.execute(
        select(WalletDiscountRule).where(
            WalletDiscountRule.client_id
            == client_id,
            WalletDiscountRule.branch_id
            == branch_id,
        )
    )

    rules = result.scalars().all()

    for rule in rules:

        is_active = rule.is_active

        if is_active is True:
            return rule

        if hasattr(is_active, "value"):
            is_active = is_active.value

        if str(is_active).strip().lower() in {
            "true",
            "1",
            "active",
            "yes",
        }:
            return rule

    return None


# ============================================================
# CALCULATE WALLET DISCOUNT
# ============================================================


async def calculate_wallet_discount(
    db,
    customer_id: int,
    client_id: int,
    branch_id: int,
    amount: float,
    lock_wallet: bool = False,
):
    """
    Calculate wallet contribution.

    Wallet is NOT a payment method.

    Example:

        Bill                  = ₹5616
        Wallet balance       = ₹2000
        Branch rule          = 20%

        Maximum wallet usage = ₹1123.20
        Wallet contribution  = ₹1123.20
        Customer pays        = ₹4492.80
    """

    amount = round(
        float(amount or 0),
        2,
    )

    empty_response = {
        "wallet_available": False,
        "wallet_balance": 0.0,
        "wallet_percent": 0.0,
        "max_wallet_discount": 0.0,
        "wallet_discount": 0.0,
    }

    if amount <= 0:
        return empty_response

    # ========================================================
    # GET WALLET
    # ========================================================

    wallet = await get_wallet_account(
        db,
        customer_id=customer_id,
        client_id=client_id,
        lock=lock_wallet,
    )

    if wallet is None:
        return empty_response

    wallet_balance = round(
        max(
            float(wallet.balance or 0),
            0.0,
        ),
        2,
    )

    if not wallet.is_active:
        return {
            "wallet_available": False,
            "wallet_balance": wallet_balance,
            "wallet_percent": 0.0,
            "max_wallet_discount": 0.0,
            "wallet_discount": 0.0,
        }

    # ========================================================
    # GET BRANCH WALLET RULE
    # ========================================================

    rule = await get_wallet_discount_rule(
        db,
        client_id=client_id,
        branch_id=branch_id,
    )

    if rule is None:
        return {
            "wallet_available": False,
            "wallet_balance": wallet_balance,
            "wallet_percent": 0.0,
            "max_wallet_discount": 0.0,
            "wallet_discount": 0.0,
        }

    wallet_percent = round(
        max(
            float(
                rule.max_wallet_discount_percent
                or 0
            ),
            0.0,
        ),
        2,
    )

    # ========================================================
    # MAX WALLET USAGE
    # ========================================================

    max_wallet_discount = round(
        amount
        * wallet_percent
        / 100,
        2,
    )

    # ========================================================
    # ACTUAL WALLET CONTRIBUTION
    # ========================================================

    wallet_discount = round(
        min(
            wallet_balance,
            max_wallet_discount,
            amount,
        ),
        2,
    )

    return {
        "wallet_available": wallet_discount > 0,
        "wallet_balance": wallet_balance,
        "wallet_percent": wallet_percent,
        "max_wallet_discount": max_wallet_discount,
        "wallet_discount": wallet_discount,
    }


# ============================================================
# DEBIT WALLET
# ============================================================


async def debit_wallet(
    db,
    customer_id: int,
    client_id: int,
    branch_id: int,
    amount: float,
    reference_type: str,
    reference_id: int,
    notes: str | None = None,
):
    """
    Deduct wallet balance.

    Wallet is NOT a payment method.
    """

    amount = round(
        float(amount or 0),
        2,
    )

    if amount <= 0:
        return None

    # ========================================================
    # DUPLICATE DEBIT CHECK
    # ========================================================

    if reference_type == "BILL":
        existing_tx = await db.execute(
            select(WalletTransaction).where(
                WalletTransaction.reference_type == "BILL",
                WalletTransaction.reference_id == reference_id,
                WalletTransaction.transaction_type == "DEBIT",
            )
        )
        if existing_tx.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=400,
                detail="Wallet has already been debited for this bill.",
            )

    # ========================================================
    # LOCK WALLET
    # ========================================================

    wallet = await get_wallet_account(
        db,
        customer_id=customer_id,
        client_id=client_id,
        lock=True,
    )

    if wallet is None:
        raise HTTPException(
            status_code=400,
            detail="Customer wallet account not found",
        )

    if not wallet.is_active:
        raise HTTPException(
            status_code=400,
            detail="Customer wallet is inactive",
        )

    current_balance = round(
        max(
            float(wallet.balance or 0),
            0.0,
        ),
        2,
    )

    if current_balance < amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient wallet balance. "
                f"Available: ₹{current_balance:.2f}, "
                f"Required: ₹{amount:.2f}"
            ),
        )

    new_balance = round(
        current_balance - amount,
        2,
    )

    wallet.balance = new_balance

    wallet.total_spent = round(
        float(wallet.total_spent or 0)
        + amount,
        2,
    )

    # ========================================================
    # CREATE TRANSACTION
    # ========================================================

    transaction = WalletTransaction(
        customer_id=customer_id,
        wallet_account_id=wallet.id,
        client_id=client_id,
        branch_id=branch_id,
        transaction_type="DEBIT",
        amount=amount,
        balance_before=current_balance,
        balance_after=new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )

    db.add(transaction)

    await db.flush()

    return transaction