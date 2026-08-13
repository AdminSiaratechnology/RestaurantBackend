"""
app/accounts/crm/wallet/service.py

Customer Wallet Services.

Includes:

- Get wallet account
- Get wallet transactions
- Loyalty Points -> Wallet Rupee conversion

IMPORTANT BUSINESS RULE:

Every successful loyalty conversion converts ALL current
loyalty points and resets them to ZERO.

The conversion does NOT modify:

- Customer total_spend
- Customer current_spend
- Customer current_rank
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.crm.customer.model import Customer

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
# GET / CREATE WALLET ACCOUNT
# ============================================================


async def get_wallet_account(
    db: AsyncSession,
    customer_id: int,
) -> Optional[CustomerWalletAccount]:

    # --------------------------------------------------------
    # Find existing wallet
    # --------------------------------------------------------

    stmt = (
        select(CustomerWalletAccount)
        .where(
            CustomerWalletAccount.customer_id
            == customer_id
        )
    )

    result = await db.execute(stmt)

    account = result.scalar_one_or_none()

    if account:

        return account

    # --------------------------------------------------------
    # Check customer
    # --------------------------------------------------------

    customer_result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id
        )
    )

    customer = customer_result.scalar_one_or_none()

    if customer is None:

        return None

    # --------------------------------------------------------
    # Create wallet
    # --------------------------------------------------------

    account = CustomerWalletAccount(
        customer_id=customer.id,
        client_id=customer.client_id,
        balance=0.0,
        total_recharged=0.0,
        total_spent=0.0,
    )

    db.add(account)

    await db.commit()

    await db.refresh(account)

    return account


# ============================================================
# GET WALLET TRANSACTIONS
# ============================================================


async def get_wallet_transactions(
    db: AsyncSession,
    customer_id: int,
) -> List[WalletTransaction]:

    stmt = (
        select(WalletTransaction)
        .where(
            WalletTransaction.customer_id
            == customer_id
        )
        .order_by(
            WalletTransaction.created_at.desc()
        )
    )

    result = await db.execute(stmt)

    return result.scalars().all()


# ============================================================
# CONVERT LOYALTY POINTS -> WALLET
# ============================================================


async def convert_loyalty_points_to_wallet(
    db: AsyncSession,
    *,
    customer_id: int,
):
    """
    Convert ALL current customer loyalty points
    into wallet money.

    Example:

        Branch Rule:
            10 points = ₹5

        Customer:
            135 points

        Conversion:
            135 / 10 * 5 = ₹67.50

        After:
            customer.loyalty_points = 0
            loyalty_account.current_points_balance = 0
            wallet.balance += 67.50

    IMPORTANT:

    This operation does NOT modify:

        customer.total_spend
        customer.current_spend
        customer.current_rank

    """

    try:

        # ====================================================
        # 1. LOCK CUSTOMER
        # ====================================================
        #
        # Prevents two conversion requests from processing
        # the same customer's points simultaneously.
        #
        # ====================================================

        customer_stmt = (
            select(Customer)
            .where(
                Customer.id == customer_id
            )
            .with_for_update()
        )

        customer_result = await db.execute(
            customer_stmt
        )

        customer = customer_result.scalar_one_or_none()

        if customer is None:

            raise ValueError(
                "Customer not found"
            )

        # ====================================================
        # 2. READ CURRENT LOYALTY POINTS
        # ====================================================

        current_points = float(
            customer.loyalty_points or 0.0
        )

        if current_points <= 0:

            raise ValueError(
                "Customer has no loyalty points available for conversion"
            )

        # ====================================================
        # 3. FIND BRANCH RULE
        # ====================================================

        rule_stmt = (
            select(LoyaltyConversionRule)
            .where(
                LoyaltyConversionRule.branch_id
                == customer.branch_id,

                LoyaltyConversionRule.is_active.is_(True),
            )
        )

        rule_result = await db.execute(
            rule_stmt
        )

        rule = rule_result.scalar_one_or_none()

        if rule is None:

            raise ValueError(
                "No active loyalty conversion rule found "
                "for customer's branch"
            )

        # ====================================================
        # 4. VALIDATE RULE
        # ====================================================

        if rule.points_required <= 0:

            raise ValueError(
                "Invalid loyalty conversion rule: "
                "points_required must be greater than zero"
            )

        if rule.rupee_value <= 0:

            raise ValueError(
                "Invalid loyalty conversion rule: "
                "rupee_value must be greater than zero"
            )

        # ====================================================
        # 5. CALCULATE RUPEE VALUE
        # ====================================================
        #
        # Example:
        #
        # 10 points = ₹5
        #
        # 135 points:
        #
        # 135 / 10 * 5
        # = ₹67.50
        #
        # ====================================================

        rupee_amount = (
            current_points
            / float(rule.points_required)
        ) * float(rule.rupee_value)

        rupee_amount = round(
            rupee_amount,
            2,
        )

        if rupee_amount <= 0:

            raise ValueError(
                "Calculated wallet amount is zero"
            )

        # ====================================================
        # 6. GET / CREATE WALLET
        # ====================================================

        wallet_stmt = (
            select(CustomerWalletAccount)
            .where(
                CustomerWalletAccount.customer_id
                == customer_id
            )
            .with_for_update()
        )

        wallet_result = await db.execute(
            wallet_stmt
        )

        wallet = wallet_result.scalar_one_or_none()

        # ----------------------------------------------------
        # Create wallet if it doesn't exist
        # ----------------------------------------------------

        if wallet is None:

            wallet = CustomerWalletAccount(
                customer_id=customer.id,
                client_id=customer.client_id,
                balance=0.0,
                total_recharged=0.0,
                total_spent=0.0,
            )

            db.add(wallet)

            await db.flush()

        # ====================================================
        # 7. GET LOYALTY ACCOUNT
        # ====================================================

        loyalty_stmt = (
            select(CustomerLoyaltyAccount)
            .where(
                CustomerLoyaltyAccount.customer_id
                == customer_id
            )
            .with_for_update()
        )

        loyalty_result = await db.execute(
            loyalty_stmt
        )

        loyalty_account = (
            loyalty_result.scalar_one_or_none()
        )

        # ====================================================
        # 8. CREATE LOYALTY ACCOUNT IF MISSING
        # ====================================================

        if loyalty_account is None:

            loyalty_account = CustomerLoyaltyAccount(
                customer_id=customer.id,
                client_id=customer.client_id,
                total_points_earned=0.0,
                total_points_redeemed=0.0,
                current_points_balance=current_points,
                converted_spend=0.0,
            )

            db.add(loyalty_account)

            await db.flush()

        # ====================================================
        # 9. GET CURRENT WALLET BALANCE
        # ====================================================

        current_wallet_balance = float(
            wallet.balance or 0.0
        )

        # ====================================================
        # 10. ADD MONEY TO WALLET
        # ====================================================

        new_wallet_balance = round(
            current_wallet_balance
            + rupee_amount,
            2,
        )

        wallet.balance = new_wallet_balance

        # ====================================================
        # 11. RESET ALL CURRENT LOYALTY POINTS
        # ====================================================
        #
        # THIS IS THE MAIN REQUIREMENT.
        #
        # Every successful conversion:
        #
        # ALL CURRENT POINTS -> ZERO
        #
        # ====================================================

        customer.loyalty_points = 0.0

        loyalty_account.current_points_balance = 0.0

        # ====================================================
        # 12. INCREASE TOTAL REDEEMED
        # ====================================================

        loyalty_account.total_points_redeemed = round(
            float(
                loyalty_account.total_points_redeemed
                or 0.0
            )
            + current_points,
            2,
        )

        # ====================================================
        # IMPORTANT:
        #
        # DO NOT CHANGE:
        #
        # customer.total_spend
        # customer.current_spend
        # customer.current_rank
        #
        # ====================================================

        # ====================================================
        # 13. CREATE LOYALTY LEDGER TRANSACTION
        # ====================================================

        loyalty_transaction = LoyaltyTransaction(
            account_id=loyalty_account.id,
            customer_id=customer.id,
            bill_id=None,

            transaction_type="CONVERSION",

            # Negative because points are consumed.
            points=-current_points,

            balance_after=0.0,

            description=(
                f"Converted {current_points:g} loyalty points "
                f"into ₹{rupee_amount:.2f}. "
                f"Conversion rate: "
                f"{rule.points_required:g} points = "
                f"₹{rule.rupee_value:.2f}"
            ),
        )

        db.add(
            loyalty_transaction
        )

        # ====================================================
        # 14. CREATE WALLET LEDGER TRANSACTION
        # ====================================================

        wallet_transaction = WalletTransaction(
            account_id=wallet.id,
            customer_id=customer.id,
            bill_id=None,

            transaction_type="LOYALTY_CONVERSION",

            amount=rupee_amount,

            balance_after=new_wallet_balance,

            remarks=(
                f"Loyalty conversion: "
                f"{current_points:g} points -> "
                f"₹{rupee_amount:.2f}. "
                f"Rate: "
                f"{rule.points_required:g} points = "
                f"₹{rule.rupee_value:.2f}"
            ),
        )

        db.add(
            wallet_transaction
        )

        # ====================================================
        # 15. COMMIT ATOMIC TRANSACTION
        # ====================================================
        #
        # Customer points reset
        # +
        # Wallet credit
        # +
        # Loyalty ledger
        # +
        # Wallet ledger
        #
        # ALL COMMIT TOGETHER.
        #
        # If anything fails -> rollback everything.
        #
        # ====================================================

        await db.commit()

        # ====================================================
        # 16. REFRESH
        # ====================================================

        await db.refresh(
            customer
        )

        await db.refresh(
            wallet
        )

        await db.refresh(
            loyalty_account
        )

        # ====================================================
        # 17. RESPONSE
        # ====================================================

        return {
            "customer_id": customer.id,

            "points_converted": current_points,

            "rupee_amount": rupee_amount,

            "conversion_rate_points": float(
                rule.points_required
            ),

            "conversion_rate_rupees": float(
                rule.rupee_value
            ),

            "loyalty_points_after": float(
                customer.loyalty_points
            ),

            "wallet_balance_after": float(
                wallet.balance
            ),

            "message": (
                f"{current_points:g} loyalty points "
                f"converted into ₹{rupee_amount:.2f} "
                f"successfully. "
                f"Loyalty points have been reset to 0."
            ),
        }

    except ValueError:
        await db.rollback()
        raise

    except Exception:
        await db.rollback()
        raise