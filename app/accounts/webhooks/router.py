from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
    status,
)

from app.accounts.webhooks.security import (
    verify_uber_signature,
)

from app.accounts.webhooks.schema import (
    UberWebhookPayload,
)

from app.accounts.webhooks.service import (
    process_uber_webhook,
    get_uber_client_secret,
)

from app.db.config import SessionDep


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)


# =========================================================
# UBER EATS WEBHOOK
# =========================================================

@router.post(
    "/uber-eats",
    status_code=status.HTTP_200_OK,
)
async def uber_eats_webhook(
    request: Request,
    db: SessionDep,
    x_uber_signature: str | None = Header(
        default=None,
        alias="X-Uber-Signature",
    ),
):

    # =====================================================
    # READ RAW BODY
    #
    # IMPORTANT:
    # Signature must be calculated against the exact
    # raw request body.
    # =====================================================

    body = await request.body()

    # =====================================================
    # SIGNATURE REQUIRED
    # =====================================================

    if not x_uber_signature:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Uber-Signature",
        )

    # =====================================================
    # GET UBER CLIENT SECRET
    # =====================================================

    client_secret = await get_uber_client_secret(
        db=db,
        request=request,
    )

    if not client_secret:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Uber client secret not configured",
        )

    # =====================================================
    # VERIFY SIGNATURE
    # =====================================================

    is_valid = verify_uber_signature(
        payload=body,
        signature=x_uber_signature,
        client_secret=client_secret,
    )

    if not is_valid:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Uber webhook signature",
        )

    # =====================================================
    # PARSE JSON
    # =====================================================

    try:

        payload = (
            UberWebhookPayload.model_validate_json(
                body
            )
        )

    except Exception as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Uber webhook payload",
        ) from exc

    # =====================================================
    # PROCESS WEBHOOK
    # =====================================================

    try:

        result = await process_uber_webhook(
            db=db,
            payload=payload,
        )

    except Exception as exc:

        # -------------------------------------------------
        # Important:
        #
        # Do NOT silently return 200 when processing failed.
        # Returning 500 allows the provider to retry.
        # -------------------------------------------------

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        ) from exc

    # =====================================================
    # SUCCESS
    # =====================================================

    return result