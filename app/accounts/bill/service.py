from io import BytesIO

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
    


