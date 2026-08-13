from io import BytesIO

from app.accounts.offer.model import OfferType
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.accounts.bill.invoice_template import InvoiceTemplate


class InvoiceService:

    @staticmethod
    async def download_invoice(
        db,
        bill_id,
        client_id,
        branch_id,
    ):

        bill = await BillService.get_bill(
            db=db,
            bill_id=bill_id,
            client_id=client_id,
            branch_id=branch_id,
        )

        if not bill:
            raise HTTPException(
                status_code=404,
                detail="Invoice not found"
            )

        pdf = BytesIO()

        InvoiceTemplate.generate(
            pdf,
            bill,
        )

        pdf.seek(0)

        return StreamingResponse(
            pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                f'attachment; filename="{bill.invoice_no}.pdf"'
            },
        )
    





def _money(value) -> float:
    return round(
        float(value or 0),
        2,
    )


def _calculate_offer_discount(
    offer,
    amount: float,
) -> float:

    if not offer:
        return 0.0

    if not offer.is_active:
        return 0.0

    if (
        offer.min_order_amount
        and amount < float(offer.min_order_amount)
    ):
        return 0.0

    if offer.offer_type == OfferType.FLAT_DISCOUNT:
        return round(
            min(
                float(offer.discount_value or 0),
                amount,
            ),
            2,
        )

    if offer.offer_type == OfferType.PERCENTAGE_OFF:
        return round(
            amount
            * (
                float(offer.discount_value or 0)
                / 100
            ),
            2,
        )

    # BUY_ONE_GET_ONE / FREE_ITEM
    # requires item-level business logic
    return 0.0


def _calculate_bill_totals(
    *,
    subtotal: float,
    tax_total: float,
    service_charge_percent: float,
    discount_amount: float,
    offer_discount: float,
    round_off_enabled: bool,
):
    subtotal = _money(subtotal)
    tax_total = _money(tax_total)
    discount_amount = _money(discount_amount)
    offer_discount = _money(offer_discount)

    service_charge_amount = _money(
        subtotal
        * (
            service_charge_percent / 100
        )
    )

    before_rounding = (
        subtotal
        + tax_total
        + service_charge_amount
        - discount_amount
    )

    before_rounding = _money(
        before_rounding
    )

    if round_off_enabled:
        rounded_total = float(
            round(before_rounding)
        )

        round_off_amount = _money(
            rounded_total
            - before_rounding
        )

        grand_total = rounded_total

    else:
        round_off_amount = 0.0
        grand_total = before_rounding

    final_amount = _money(
        max(
            grand_total
            - offer_discount,
            0,
        )
    )

    return {
        "service_charge_amount":
            service_charge_amount,

        "round_off_amount":
            round_off_amount,

        "grand_total":
            grand_total,

        "final_amount":
            final_amount,
    }