"""
app/accounts/crm/wallet/router.py

FastAPI router for Customer Wallet.
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
    db: SessionDep,
):

    account = await service.get_wallet_account(
        db,
        customer_id,
    )

    if account is None:

        raise HTTPException(
            status_code=404,
            detail="Wallet account not found",
        )

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
        customer_id,
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
    db: SessionDep,
):

    try:

        result = (
            await service.convert_loyalty_points_to_wallet(
                db,
                customer_id=customer_id,
            )
        )

        return result

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to convert loyalty points "
                "into wallet balance"
            ),
        )