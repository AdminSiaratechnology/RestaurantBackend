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
from app.utils.currency_formatter import format_currency, get_branch_currency_settings


def safe_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def generate_invoice_pdf(bill):

    buffer = BytesIO()
    branch = getattr(bill, "branch", None)
    _, symbol, decimals = get_branch_currency_settings(branch)
    fmt_money = lambda v: format_currency(v, currency_symbol=symbol, decimal_places=decimals)

    tax_type = str(getattr(branch, "tax_type", "GST") or "GST").upper()

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
    branch_name = getattr(branch, "name", None) if branch else "RESTAURANT"
    branch_address = getattr(branch, "address", None) if branch else ""

    elements.append(
        Paragraph(
            str(branch_name).upper(),
            title,
        )
    )

    if branch_address:
        elements.append(
            Paragraph(
                str(branch_address),
                styles["BodyText"],
            )
        )

    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            f"<b>Invoice:</b> {getattr(bill, 'invoice_no', '-') or '-'}",
            styles["BodyText"],
        )
    )

    created_at = getattr(bill, "created_at", None)
    elements.append(
        Paragraph(
            f"<b>Date:</b> {created_at.strftime('%d-%m-%Y %H:%M') if created_at else '-'}",
            styles["BodyText"],
        )
    )

    elements.append(
        Paragraph(
            f"<b>Customer:</b> {getattr(bill, 'customer_name', 'Walk In') or 'Walk In'}",
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

    order = getattr(bill, "order", None)
    order_items = getattr(order, "order_items", []) if order else []
    for item in order_items:
        item_obj = getattr(item, "item", None)
        item_name = getattr(item_obj, "name", "Item") if item_obj else "Item"
        qty = int(safe_float(getattr(item, "quantity", 1)))
        price = safe_float(getattr(item, "total_price", getattr(item, "unit_price", 0) * qty))

        data.append([
            str(item_name),
            str(qty),
            fmt_money(price),
        ])

    table = Table(
        data,
        colWidths=[90, 35, 50],
    )

    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ])
    )

    elements.append(Spacer(1, 10))

    subtotal = safe_float(getattr(bill, "subtotal", 0))
    elements.append(
        Paragraph(
            f"<b>Subtotal:</b> {fmt_money(subtotal)}",
            styles["BodyText"],
        )
    )

    tax_type = str(getattr(bill, "tax_type", None) or getattr(branch, "tax_type", "GST") or "GST").upper()
    cgst_percent = safe_float(getattr(bill, "cgst_percent", 0))
    sgst_percent = safe_float(getattr(bill, "sgst_percent", 0))
    cgst_amount = safe_float(getattr(bill, "cgst_amount", 0))
    sgst_amount = safe_float(getattr(bill, "sgst_amount", 0))
    vat_percent = safe_float(getattr(bill, "vat_percent", 0))
    vat_amount = safe_float(getattr(bill, "vat_amount", 0))
    tax_total = safe_float(getattr(bill, "tax_total", 0))

    if tax_type == "VAT":
        v_amount = vat_amount if vat_amount > 0 else tax_total
        v_percent = vat_percent if vat_percent > 0 else (cgst_percent + sgst_percent)
        if v_percent == 0 and subtotal > 0 and v_amount > 0:
            v_percent = round((v_amount / subtotal) * 100, 2)
        if v_amount > 0 or v_percent > 0:
            elements.append(
                Paragraph(
                    f"<b>VAT ({v_percent:g}%):</b> {fmt_money(v_amount)}",
                    styles["BodyText"],
                )
            )
    else:
        if cgst_amount > 0:
            elements.append(
                Paragraph(
                    f"<b>CGST ({cgst_percent:g}%):</b> {fmt_money(cgst_amount)}",
                    styles["BodyText"],
                )
            )
        if sgst_amount > 0:
            elements.append(
                Paragraph(
                    f"<b>SGST ({sgst_percent:g}%):</b> {fmt_money(sgst_amount)}",
                    styles["BodyText"],
                )
            )

    discount_amount = safe_float(getattr(bill, "discount_amount", 0))
    offer_discount = safe_float(getattr(bill, "offer_discount", 0))
    if discount_amount > 0:
        elements.append(
            Paragraph(
                f"<b>Discount:</b> -{fmt_money(discount_amount)}",
                styles["BodyText"],
            )
        )
    if offer_discount > 0:
        elements.append(
            Paragraph(
                f"<b>Offer Discount:</b> -{fmt_money(offer_discount)}",
                styles["BodyText"],
            )
        )

    final_amount = safe_float(getattr(bill, "final_amount", getattr(bill, "grand_total", 0)))
    elements.append(
        Paragraph(
            f"<b>Grand Total:</b> {fmt_money(final_amount)}",
            styles["Heading3"],
        )
    )

    elements.append(Spacer(1, 15))

    elements.append(
        Paragraph(
            str(getattr(bill, "footer_message", None) or "Thank you for dining with us!"),
            title,
        )
    )

    doc.build(elements)

    buffer.seek(0)

    return buffer