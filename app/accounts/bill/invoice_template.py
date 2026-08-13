
# app/accounts/bill/invoice_template.py

import logging
import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)

logger = logging.getLogger(__name__)


# =========================================================
# CURRENCY
# =========================================================

RUPEE = "\u20B9"


def money(value) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0

    return f"{RUPEE}{amount:,.2f}"


# =========================================================
# FONT
# =========================================================

def _get_font_paths():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    candidate_dirs = [
        os.path.abspath(
            os.path.join(
                base_dir,
                "..",
                "..",
                "assets",
                "fonts",
            )
        ),
        os.path.abspath(
            os.path.join(
                base_dir,
                "..",
                "assets",
                "fonts",
            )
        ),
        os.path.abspath(
            os.path.join(
                os.getcwd(),
                "app",
                "assets",
                "fonts",
            )
        ),
        os.path.abspath(
            os.path.join(
                os.getcwd(),
                "assets",
                "fonts",
            )
        ),
    ]

    for font_dir in candidate_dirs:

        regular = os.path.join(
            font_dir,
            "NotoSans-Regular.ttf",
        )

        bold = os.path.join(
            font_dir,
            "NotoSans-Bold.ttf",
        )

        if (
            os.path.exists(regular)
            and os.path.exists(bold)
        ):
            return regular, bold

    return None, None


def register_fonts():

    regular_name = "NotoSans"
    bold_name = "NotoSans-Bold"

    registered = pdfmetrics.getRegisteredFontNames()

    if (
        regular_name in registered
        and bold_name in registered
    ):
        return regular_name, bold_name

    regular_path, bold_path = _get_font_paths()

    if regular_path and bold_path:

        try:

            if regular_name not in registered:
                pdfmetrics.registerFont(
                    TTFont(
                        regular_name,
                        regular_path,
                    )
                )

            if bold_name not in registered:
                pdfmetrics.registerFont(
                    TTFont(
                        bold_name,
                        bold_path,
                    )
                )

            return regular_name, bold_name

        except Exception as exc:
            logger.error(
                "Failed to register NotoSans: %s",
                exc,
            )

    logger.warning(
        "NotoSans font not found. Using Helvetica."
    )

    return "Helvetica", "Helvetica-Bold"


# =========================================================
# SAFE VALUE
# =========================================================

def safe_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


# =========================================================
# INVOICE PDF
# =========================================================

class InvoiceTemplate:

    @staticmethod
    def generate(buffer: BytesIO, bill):

        font_regular, font_bold = register_fonts()

        # -------------------------------------------------
        # 80mm THERMAL RECEIPT
        # -------------------------------------------------

        doc = SimpleDocTemplate(
            buffer,
            pagesize=(
                80 * mm,
                300 * mm,
            ),
            rightMargin=4 * mm,
            leftMargin=4 * mm,
            topMargin=4 * mm,
            bottomMargin=4 * mm,
        )

        # =================================================
        # STYLES
        # =================================================

        restaurant_style = ParagraphStyle(
            "Restaurant",
            fontName=font_bold,
            fontSize=13,
            leading=15,
            alignment=TA_CENTER,
            spaceAfter=2,
        )

        address_style = ParagraphStyle(
            "Address",
            fontName=font_regular,
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
        )

        normal_style = ParagraphStyle(
            "NormalInvoice",
            fontName=font_regular,
            fontSize=7.5,
            leading=9,
        )

        bold_style = ParagraphStyle(
            "BoldInvoice",
            fontName=font_bold,
            fontSize=7.5,
            leading=9,
        )

        total_style = ParagraphStyle(
            "Total",
            fontName=font_bold,
            fontSize=10,
            leading=12,
        )

        footer_style = ParagraphStyle(
            "Footer",
            fontName=font_regular,
            fontSize=7.5,
            leading=9,
            alignment=TA_CENTER,
        )

        elements = []

        # =================================================
        # RESTAURANT
        # =================================================

        branch = getattr(
            bill,
            "branch",
            None,
        )

        branch_name = (
            getattr(
                branch,
                "name",
                None,
            )
            or "RESTAURANT"
        )

        branch_address = (
            getattr(
                branch,
                "address",
                None,
            )
            or ""
        )

        elements.append(
            Paragraph(
                str(branch_name).upper(),
                restaurant_style,
            )
        )

        if branch_address:
            elements.append(
                Paragraph(
                    str(branch_address),
                    address_style,
                )
            )

        elements.append(
            Spacer(
                1,
                4,
            )
        )

        # =================================================
        # HEADER LINE
        # =================================================

        header_line = Table(
            [[""]],
            colWidths=[72 * mm],
            rowHeights=[0.5],
        )

        header_line.setStyle(
            TableStyle([
                (
                    "LINEABOVE",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),
            ])
        )

        elements.append(header_line)

        elements.append(
            Spacer(
                1,
                4,
            )
        )

        # =================================================
        # BILL INFORMATION
        # =================================================

        invoice_no = (
            getattr(
                bill,
                "invoice_no",
                None,
            )
            or "-"
        )

        created_at = getattr(
            bill,
            "created_at",
            None,
        )

        if created_at:
            date_text = created_at.strftime(
                "%d-%m-%Y %H:%M"
            )
        else:
            date_text = "-"

        customer_name = (
            getattr(
                bill,
                "customer_name",
                None,
            )
            or "Walk In"
        )

        customer_phone = (
            getattr(
                bill,
                "customer_phone",
                None,
            )
            or ""
        )

        bill_info = [
            [
                Paragraph(
                    "<b>Invoice</b>",
                    normal_style,
                ),
                Paragraph(
                    str(invoice_no),
                    normal_style,
                ),
            ],
            [
                Paragraph(
                    "<b>Date</b>",
                    normal_style,
                ),
                Paragraph(
                    date_text,
                    normal_style,
                ),
            ],
            [
                Paragraph(
                    "<b>Customer</b>",
                    normal_style,
                ),
                Paragraph(
                    str(customer_name),
                    normal_style,
                ),
            ],
        ]

        if customer_phone:
            bill_info.append(
                [
                    Paragraph(
                        "<b>Phone</b>",
                        normal_style,
                    ),
                    Paragraph(
                        str(customer_phone),
                        normal_style,
                    ),
                ]
            )

        bill_info_table = Table(
            bill_info,
            colWidths=[
                25 * mm,
                47 * mm,
            ],
        )

        bill_info_table.setStyle(
            TableStyle([
                (
                    "ALIGN",
                    (1, 0),
                    (1, -1),
                    "RIGHT",
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    1,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    1,
                ),
            ])
        )

        elements.append(
            bill_info_table
        )

        elements.append(
            Spacer(
                1,
                5,
            )
        )

        # =================================================
        # ITEMS
        # =================================================

        item_data = [
            [
                Paragraph(
                    "<b>Item</b>",
                    bold_style,
                ),
                Paragraph(
                    "<b>Qty</b>",
                    bold_style,
                ),
                Paragraph(
                    "<b>Price</b>",
                    bold_style,
                ),
                Paragraph(
                    "<b>Amount</b>",
                    bold_style,
                ),
            ]
        ]

        order = getattr(
            bill,
            "order",
            None,
        )

        order_items = (
            getattr(
                order,
                "order_items",
                [],
            )
            if order
            else []
        )

        for order_item in order_items:

            item = getattr(
                order_item,
                "item",
                None,
            )

            item_name = (
                getattr(
                    item,
                    "name",
                    None,
                )
                if item
                else None
            ) or "Item"

            quantity = safe_float(
                getattr(
                    order_item,
                    "quantity",
                    1,
                )
            )

            if quantity <= 0:
                quantity = 1

            unit_price = getattr(
                order_item,
                "unit_price",
                None,
            )

            if unit_price is None:
                unit_price = getattr(
                    order_item,
                    "price",
                    0,
                )

            unit_price = safe_float(
                unit_price
            )

            total_price = getattr(
                order_item,
                "total_price",
                None,
            )

            if total_price is None:
                total_price = (
                    unit_price
                    * quantity
                )

            total_price = safe_float(
                total_price
            )

            item_data.append(
                [
                    Paragraph(
                        str(item_name),
                        normal_style,
                    ),
                    Paragraph(
                        str(int(quantity)),
                        normal_style,
                    ),
                    Paragraph(
                        money(unit_price),
                        normal_style,
                    ),
                    Paragraph(
                        money(total_price),
                        normal_style,
                    ),
                ]
            )

        item_table = Table(
            item_data,
            colWidths=[
                30 * mm,
                10 * mm,
                15 * mm,
                17 * mm,
            ],
            repeatRows=1,
        )

        item_table.setStyle(
            TableStyle([
                (
                    "LINEABOVE",
                    (0, 0),
                    (-1, 0),
                    0.5,
                    colors.grey,
                ),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, 0),
                    0.5,
                    colors.grey,
                ),
                (
                    "ALIGN",
                    (1, 1),
                    (1, -1),
                    "CENTER",
                ),
                (
                    "ALIGN",
                    (2, 1),
                    (-1, -1),
                    "RIGHT",
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    1,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    1,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
            ])
        )

        elements.append(
            item_table
        )

        elements.append(
            Spacer(
                1,
                5,
            )
        )

        # =================================================
        # BILL TOTALS
        # =================================================

        subtotal = safe_float(
            getattr(
                bill,
                "subtotal",
                0,
            )
        )

        cgst_amount = safe_float(
            getattr(
                bill,
                "cgst_amount",
                0,
            )
        )

        sgst_amount = safe_float(
            getattr(
                bill,
                "sgst_amount",
                0,
            )
        )

        service_charge_amount = safe_float(
            getattr(
                bill,
                "service_charge_amount",
                0,
            )
        )

        service_charge_percent = safe_float(
            getattr(
                bill,
                "service_charge_percent",
                0,
            )
        )

        cgst_percent = safe_float(
            getattr(
                bill,
                "cgst_percent",
                0,
            )
        )

        sgst_percent = safe_float(
            getattr(
                bill,
                "sgst_percent",
                0,
            )
        )

        discount_amount = safe_float(
            getattr(
                bill,
                "discount_amount",
                0,
            )
        )

        offer_discount = safe_float(
            getattr(
                bill,
                "offer_discount",
                0,
            )
        )

        round_off_amount = safe_float(
            getattr(
                bill,
                "round_off_amount",
                0,
            )
        )

        grand_total = safe_float(
            getattr(
                bill,
                "grand_total",
                0,
            )
        )

        final_amount = getattr(
            bill,
            "final_amount",
            None,
        )

        if final_amount is None:
            final_amount = grand_total
        else:
            final_amount = safe_float(
                final_amount
            )

        totals = []

        totals.append(
            [
                Paragraph(
                    "Subtotal",
                    normal_style,
                ),
                Paragraph(
                    money(subtotal),
                    normal_style,
                ),
            ]
        )

        if service_charge_amount > 0:
            totals.append(
                [
                    Paragraph(
                        f"Service Charge "
                        f"({service_charge_percent:g}%)",
                        normal_style,
                    ),
                    Paragraph(
                        money(
                            service_charge_amount
                        ),
                        normal_style,
                    ),
                ]
            )

        if cgst_amount > 0:
            totals.append(
                [
                    Paragraph(
                        f"CGST "
                        f"({cgst_percent:g}%)",
                        normal_style,
                    ),
                    Paragraph(
                        money(cgst_amount),
                        normal_style,
                    ),
                ]
            )

        if sgst_amount > 0:
            totals.append(
                [
                    Paragraph(
                        f"SGST "
                        f"({sgst_percent:g}%)",
                        normal_style,
                    ),
                    Paragraph(
                        money(sgst_amount),
                        normal_style,
                    ),
                ]
            )

        total_discount = (
            discount_amount
            + offer_discount
        )

        if total_discount > 0:
            totals.append(
                [
                    Paragraph(
                        "Discount",
                        normal_style,
                    ),
                    Paragraph(
                        f"-{money(total_discount)}",
                        normal_style,
                    ),
                ]
            )

        if round_off_amount != 0:
            totals.append(
                [
                    Paragraph(
                        "Round Off",
                        normal_style,
                    ),
                    Paragraph(
                        money(
                            round_off_amount
                        ),
                        normal_style,
                    ),
                ]
            )

        totals.append(
            [
                Paragraph(
                    "<b>Grand Total</b>",
                    total_style,
                ),
                Paragraph(
                    f"<b>{money(grand_total)}</b>",
                    total_style,
                ),
            ]
        )

        if abs(
            final_amount - grand_total
        ) > 0.001:

            totals.append(
                [
                    Paragraph(
                        "<b>Final Amount</b>",
                        total_style,
                    ),
                    Paragraph(
                        f"<b>{money(final_amount)}</b>",
                        total_style,
                    ),
                ]
            )

        totals_table = Table(
            totals,
            colWidths=[
                40 * mm,
                32 * mm,
            ],
        )

        totals_table.setStyle(
            TableStyle([
                (
                    "ALIGN",
                    (1, 0),
                    (1, -1),
                    "RIGHT",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "LINEABOVE",
                    (0, -1),
                    (-1, -1),
                    0.7,
                    colors.black,
                ),
            ])
        )

        elements.append(
            totals_table
        )

        # =================================================
        # PAYMENT
        # =================================================

        paid_amount = safe_float(
            getattr(
                bill,
                "paid_amount",
                0,
            )
        )

        due_amount = getattr(
            bill,
            "due_amount",
            None,
        )

        if due_amount is None:
            due_amount = max(
                final_amount
                - paid_amount,
                0,
            )

        due_amount = safe_float(
            due_amount
        )

        payment_method = getattr(
            bill,
            "payment_method",
            None,
        )

        payment_status = getattr(
            bill,
            "payment_status",
            None,
        )

        elements.append(
            Spacer(
                1,
                5,
            )
        )

        payment_data = [
            [
                Paragraph(
                    "<b>Paid</b>",
                    normal_style,
                ),
                Paragraph(
                    money(paid_amount),
                    normal_style,
                ),
            ],
            [
                Paragraph(
                    "<b>Due</b>",
                    normal_style,
                ),
                Paragraph(
                    money(due_amount),
                    normal_style,
                ),
            ],
        ]

        if payment_method:
            payment_data.append(
                [
                    Paragraph(
                        "<b>Payment Method</b>",
                        normal_style,
                    ),
                    Paragraph(
                        str(payment_method),
                        normal_style,
                    ),
                ]
            )

        if payment_status:

            status_text = (
                payment_status.value
                if hasattr(
                    payment_status,
                    "value",
                )
                else str(payment_status)
            )

            payment_data.append(
                [
                    Paragraph(
                        "<b>Status</b>",
                        normal_style,
                    ),
                    Paragraph(
                        status_text.upper(),
                        normal_style,
                    ),
                ]
            )

        payment_table = Table(
            payment_data,
            colWidths=[
                40 * mm,
                32 * mm,
            ],
        )

        payment_table.setStyle(
            TableStyle([
                (
                    "ALIGN",
                    (1, 0),
                    (1, -1),
                    "RIGHT",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    2,
                ),
            ])
        )

        elements.append(
            payment_table
        )

        # =================================================
        # FOOTER
        # =================================================

        elements.append(
            Spacer(
                1,
                8,
            )
        )

        footer_line = Table(
            [[""]],
            colWidths=[72 * mm],
            rowHeights=[0.5],
        )

        footer_line.setStyle(
            TableStyle([
                (
                    "LINEABOVE",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),
            ])
        )

        elements.append(
            footer_line
        )

        elements.append(
            Spacer(
                1,
                5,
            )
        )

        footer_message = (
            getattr(
                bill,
                "footer_message",
                None,
            )
            or "Thank you for dining with us!"
        )

        elements.append(
            Paragraph(
                str(footer_message),
                footer_style,
            )
        )

        # =================================================
        # BUILD
        # =================================================

        doc.build(elements)

        buffer.seek(0)

        return buffer

