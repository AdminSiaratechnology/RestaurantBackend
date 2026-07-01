

from io import BytesIO

from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib import colors


def generate_invoice_pdf(bill):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=(80 * mm, 300 * mm),
        rightMargin=5,
        leftMargin=5,
        topMargin=5,
        bottomMargin=5,
    )

    styles = getSampleStyleSheet()

    title = styles["Heading2"]
    title.alignment = TA_CENTER

    elements = []

    # Restaurant Name
    elements.append(
        Paragraph(
            bill.branch.name,
            title,
        )
    )

    elements.append(
        Paragraph(
            bill.branch.address or "",
            styles["BodyText"],
        )
    )

    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            f"<b>Invoice:</b> {bill.invoice_no}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"<b>Date:</b> {bill.created_at.strftime('%d-%m-%Y %H:%M')}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"<b>Customer:</b> {bill.customer_name or 'Walk In'}",
            styles["BodyText"],
        )
    )

    elements.append(Spacer(1, 8))

    data = [
        [
            "Item",
            "Qty",
            "Price",
        ]
    ]

    for item in bill.order.order_items:

        data.append([
            item.item.name,
            str(item.quantity),
            f"{item.total_price:.2f}",
        ])

    table = Table(
        data,
        colWidths=[90, 35, 50],
    )

    table.setStyle(
        TableStyle([
            ("GRID",(0,0),(-1,-1),0.5,colors.black),
            ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
            ("ALIGN",(1,1),(-1,-1),"CENTER"),
        ])
    )

    elements.append(table)

    elements.append(Spacer(1,10))

    elements.append(
        Paragraph(
            f"<b>Subtotal:</b> ₹{bill.subtotal:.2f}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"<b>CGST:</b> ₹{bill.cgst_amount:.2f}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"<b>SGST:</b> ₹{bill.sgst_amount:.2f}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"<b>Discount:</b> ₹{bill.offer_discount:.2f}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"<b>Grand Total:</b> ₹{bill.final_amount:.2f}",
            styles["Heading3"],
        )
    )

    elements.append(Spacer(1,15))

    elements.append(
        Paragraph(
            bill.footer_message or "",
            title,
        )
    )

    doc.build(elements)

    buffer.seek(0)

    return buffer