"""
FastAPI router for CRM Wallet.
"""

from typing import List

from fastapi import (
    APIRouter,
    HTTPException,
)

from app.db.config import SessionDep

from app.accounts.crm.wallet import service

from app.accounts.crm.wallet.schema import (
    WalletAccountOut,
    WalletTransactionOut,
    LoyaltyToWalletConversionOut,
)


router = APIRouter(
    prefix="/crm/wallet",
    tags=["CRM Wallet"],
)


# ============================================================
# GET WALLET ACCOUNT
# ============================================================


@router.get(
    "/account",
    response_model=WalletAccountOut,
)
async def get_account(
    customer_id: int,
    client_id: int,
    db: SessionDep,
):
    account = await service.get_wallet_account(
        db,
        customer_id=customer_id,
        client_id=client_id,
    )

    if account is None:
        account = await service.get_or_create_wallet_account(
            db,
            customer_id=customer_id,
            client_id=client_id,
        )

        await db.commit()
        await db.refresh(account)

    return account


# ============================================================
# GET WALLET TRANSACTIONS
# ============================================================


@router.get(
    "/transactions",
    response_model=List[WalletTransactionOut],
)
async def list_transactions(
    customer_id: int,
    db: SessionDep,
):
    return await service.get_wallet_transactions(
        db,
        customer_id=customer_id,
    )


# ============================================================
# LOYALTY -> WALLET CONVERSION
# ============================================================


@router.post(
    "/convert-loyalty/{customer_id}",
    response_model=LoyaltyToWalletConversionOut,
)
async def convert_loyalty_to_wallet(
    customer_id: int,
    branch_id: int,
    db: SessionDep,
):
    try:

        result = await service.convert_loyalty_points_to_wallet(
            db,
            customer_id=customer_id,
            branch_id=branch_id,
        )

        return result

    except HTTPException:
        await db.rollback()
        raise

    except ValueError as exc:
        await db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        await db.rollback()

        print(
            "LOYALTY TO WALLET ROUTER ERROR:",
            repr(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to convert loyalty points "
                "into wallet balance"
            ),
        )