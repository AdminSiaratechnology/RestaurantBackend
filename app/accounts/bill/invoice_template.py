import logging
import os

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Reusable Currency Helper
# ---------------------------------------------------------
RUPEE = "\u20B9"


def money(value) -> str:
    """Format numeric values with Indian Rupee (₹) symbol."""
    try:
        val = float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        val = 0.0
    return f"{RUPEE}{val:,.2f}"


# ---------------------------------------------------------
# Robust Font Management (Loaded & Registered Once)
# ---------------------------------------------------------
def _get_font_paths() -> tuple[str, str]:
    """Locate NotoSans font files across multiple candidate locations for cross-platform support."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_dirs = [
        # Primary path relative to app/accounts/bill/ -> app/assets/fonts/
        os.path.abspath(os.path.join(base_dir, "..", "..", "assets", "fonts")),
        # Secondary fallback relative to app/ -> app/assets/fonts/
        os.path.abspath(os.path.join(base_dir, "..", "assets", "fonts")),
        # CWD fallback options for containerized/deployed envs (e.g. Render/Docker root)
        os.path.abspath(os.path.join(os.getcwd(), "app", "assets", "fonts")),
        os.path.abspath(os.path.join(os.getcwd(), "assets", "fonts")),
    ]

    for fdir in candidate_dirs:
        reg_path = os.path.join(fdir, "NotoSans-Regular.ttf")
        bold_path = os.path.join(fdir, "NotoSans-Bold.ttf")
        if os.path.exists(reg_path) and os.path.exists(bold_path):
            return reg_path, bold_path

    # Primary path fallback for logging error context if files missing
    primary_dir = os.path.abspath(os.path.join(base_dir, "..", "..", "assets", "fonts"))
    return (
        os.path.join(primary_dir, "NotoSans-Regular.ttf"),
        os.path.join(primary_dir, "NotoSans-Bold.ttf"),
    )


def register_fonts() -> tuple[str, str]:
    """
    Registers NotoSans fonts with ReportLab pdfmetrics exactly once.
    Returns (font_regular, font_bold) font names.
    Falls back to Helvetica ONLY if font files are actually missing.
    """
    font_regular = "NotoSans"
    font_bold = "NotoSans-Bold"

    registered = pdfmetrics.getRegisteredFontNames()
    if font_regular in registered and font_bold in registered:
        return font_regular, font_bold

    reg_path, bold_path = _get_font_paths()

    if os.path.exists(reg_path) and os.path.exists(bold_path):
        try:
            if font_regular not in registered:
                pdfmetrics.registerFont(TTFont(font_regular, reg_path))
            if font_bold not in registered:
                pdfmetrics.registerFont(TTFont(font_bold, bold_path))
            logger.info("Successfully registered NotoSans fonts for PDF invoice generation.")
            return font_regular, font_bold
        except Exception as err:
            logger.error(f"Error registering NotoSans fonts: {err}. Falling back to Helvetica.")
    else:
        logger.error(
            f"Unicode font files missing from expected path ({reg_path}, {bold_path}). "
            "Falling back to Helvetica. Indian Rupee symbol (₹) may not render correctly."
        )

    # Fallback to standard Helvetica if font files missing or registration failed
    return "Helvetica", "Helvetica-Bold"


class InvoiceTemplate:

    @staticmethod
    def generate(buffer, bill):
        font_regular, font_bold = register_fonts()

        pdf = canvas.Canvas(
            buffer,
            pagesize=(120 * mm, 250 * mm),
        )

        y = 230 * mm

        # -------------------------
        # Header
        # -------------------------
        pdf.setFont(font_bold, 16)
        pdf.drawCentredString(
            60 * mm,
            y,
            bill.branch.name.upper()
            if bill.branch and getattr(bill.branch, "name", None)
            else "DELICIUS",
        )

        y -= 6 * mm

        pdf.setFont(font_regular, 9)
        pdf.drawCentredString(
            60 * mm,
            y,
            "GSTIN: XXXXXXXXXXXXXXX",
        )

        y -= 8 * mm

        def draw_dashed_line(y_pos):
            pdf.setDash(2, 2)
            pdf.setStrokeColor(colors.lightgrey)
            pdf.line(10 * mm, y_pos, 110 * mm, y_pos)
            pdf.setDash()
            pdf.setStrokeColor(colors.black)

        draw_dashed_line(y)

        # -------------------------
        # Invoice Info
        # -------------------------
        y -= 6 * mm

        pdf.setFont(font_regular, 10)

        pdf.drawString(10 * mm, y, "Invoice No")
        pdf.drawRightString(110 * mm, y, str(getattr(bill, "invoice_no", "")))

        y -= 6 * mm

        pdf.drawString(10 * mm, y, "Date")
        billed_at = getattr(bill, "billed_at", None)
        date_str = billed_at.strftime("%d %b %Y") if billed_at else ""
        pdf.drawRightString(110 * mm, y, date_str)

        y -= 6 * mm

        pdf.drawString(10 * mm, y, "Customer")
        pdf.drawRightString(
            110 * mm,
            y,
            getattr(bill, "customer_name", None) or "Guest",
        )

        y -= 8 * mm
        draw_dashed_line(y)

        # -------------------------
        # Items
        # -------------------------
        y -= 6 * mm

        pdf.setFont(font_bold, 10)
        pdf.drawString(10 * mm, y, "Items")

        y -= 8 * mm

        pdf.setFont(font_bold, 8)
        pdf.setFillColor(colors.HexColor("#4A6076"))

        pdf.drawString(10 * mm, y, "ITEM")
        pdf.drawCentredString(65 * mm, y, "QTY")
        pdf.drawRightString(85 * mm, y, "PRICE")
        pdf.drawRightString(110 * mm, y, "AMOUNT")

        pdf.setFillColor(colors.black)

        y -= 6 * mm

        pdf.setFont(font_regular, 9)

        if bill.order and hasattr(bill.order, "order_items"):
            for order_item in bill.order.order_items:
                item_name = order_item.item.name if (order_item.item and hasattr(order_item.item, "name")) else ""
                pdf.drawString(10 * mm, y, item_name)

                pdf.drawCentredString(
                    65 * mm,
                    y,
                    str(getattr(order_item, "quantity", 1)),
                )

                # 1. Item Price field
                pdf.drawRightString(
                    85 * mm,
                    y,
                    money(getattr(order_item, "price", 0)),
                )

                # 2. Item Amount field
                pdf.drawRightString(
                    110 * mm,
                    y,
                    money(getattr(order_item, "total_price", 0)),
                )

                y -= 6 * mm

        y -= 2 * mm

        draw_dashed_line(y)

        # -------------------------
        # Totals
        # -------------------------
        y -= 6 * mm

        pdf.setFont(font_regular, 9)
        pdf.drawString(10 * mm, y, "Subtotal")
        # 3. Subtotal field
        pdf.drawRightString(
            110 * mm,
            y,
            money(getattr(bill, "subtotal", 0)),
        )

        service_charge_amount = getattr(bill, "service_charge_amount", 0)
        if service_charge_amount and service_charge_amount > 0:
            y -= 6 * mm
            service_charge_percent = getattr(bill, "service_charge_percent", 0)
            pdf.drawString(
                10 * mm,
                y,
                f"Service Charge ({service_charge_percent}%)",
            )
            # 4. Service Charge field
            pdf.drawRightString(
                110 * mm,
                y,
                money(service_charge_amount),
            )

        cgst_amount = getattr(bill, "cgst_amount", 0)
        if cgst_amount and cgst_amount > 0:
            y -= 6 * mm
            pdf.drawString(10 * mm, y, "CGST")
            # 5. CGST field
            pdf.drawRightString(
                110 * mm,
                y,
                money(cgst_amount),
            )

        sgst_amount = getattr(bill, "sgst_amount", 0)
        if sgst_amount and sgst_amount > 0:
            y -= 6 * mm
            pdf.drawString(10 * mm, y, "SGST")
            # 6. SGST field
            pdf.drawRightString(
                110 * mm,
                y,
                money(sgst_amount),
            )

        round_off_amount = getattr(bill, "round_off_amount", 0)
        if round_off_amount != 0:
            y -= 6 * mm
            pdf.drawString(10 * mm, y, "Round Off")
            # 7. Round Off field
            pdf.drawRightString(
                110 * mm,
                y,
                money(round_off_amount),
            )

        # -------------------------
        # Grand Total
        # -------------------------
        y -= 8 * mm
        draw_dashed_line(y)

        y -= 8 * mm

        pdf.setFont(font_bold, 11)
        pdf.setFillColor(colors.HexColor("#FF4500"))

        pdf.drawString(10 * mm, y, "Grand Total")

        # 8. Grand Total field
        pdf.drawRightString(
            110 * mm,
            y,
            money(getattr(bill, "grand_total", 0)),
        )

        pdf.setFillColor(colors.black)

        y -= 8 * mm
        draw_dashed_line(y)

        # -------------------------
        # Payment
        # -------------------------
        paid_amount = getattr(bill, "paid_amount", 0) or 0
        due_amount = getattr(bill, "due_amount", None)
        if due_amount is None:
            due_amount = getattr(bill, "grand_total", 0) or 0

        y -= 8 * mm

        pdf.setFont(font_bold, 10)
        pdf.setFillColor(colors.green)

        pdf.drawString(10 * mm, y, "Paid")
        # 9. Paid Amount field
        pdf.drawRightString(
            110 * mm,
            y,
            money(paid_amount),
        )

        pdf.setFillColor(colors.black)

        y -= 6 * mm

        pdf.setFont(font_regular, 10)

        pdf.drawString(10 * mm, y, "Due")
        # 10. Due Amount field
        pdf.drawRightString(
            110 * mm,
            y,
            money(due_amount),
        )

        # -------------------------
        # Footer
        # -------------------------
        y -= 8 * mm
        draw_dashed_line(y)

        y -= 10 * mm

        pdf.setFont(font_regular, 9)
        pdf.setFillColor(colors.grey)

        pdf.drawCentredString(
            60 * mm,
            y,
            getattr(bill, "footer_message", None) or "Thank you for dining with us!",
        )

        pdf.save()