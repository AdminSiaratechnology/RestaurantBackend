import os
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors

class InvoiceTemplate:

    @staticmethod
    def generate(buffer, bill):
        
        # Load Arial font to support the Rupee symbol (₹)
        has_arial = os.path.exists("C:\\Windows\\Fonts\\arial.ttf")
        if has_arial:
            pdfmetrics.registerFont(TTFont('Arial', 'C:\\Windows\\Fonts\\arial.ttf'))
            pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:\\Windows\\Fonts\\arialbd.ttf'))
            pdfmetrics.registerFont(TTFont('Arial-Italic', 'C:\\Windows\\Fonts\\ariali.ttf'))
            font_regular = "Arial"
            font_bold = "Arial-Bold"
            font_italic = "Arial-Italic"
        else:
            font_regular = "Helvetica"
            font_bold = "Helvetica-Bold"
            font_italic = "Helvetica-Oblique"

        pdf = canvas.Canvas(
            buffer,
            pagesize=(120 * mm, 250 * mm),
        )

        y = 230 * mm
        
        pdf.setFont(font_bold, 16)
        pdf.drawCentredString(60 * mm, y, bill.branch.name.upper() if bill.branch and bill.branch.name else "DELICIUS")
        
        y -= 6 * mm
        pdf.setFont(font_regular, 9)
        pdf.drawCentredString(60 * mm, y, "GSTIN: XXXXXXXXXXXXXXX")

        y -= 8 * mm
        
        def draw_dashed_line(y_pos):
            pdf.setDash(2, 2)
            pdf.setStrokeColor(colors.lightgrey)
            pdf.line(10 * mm, y_pos, 110 * mm, y_pos)
            pdf.setDash()
            pdf.setStrokeColor(colors.black)
            
        draw_dashed_line(y)
        
        y -= 6 * mm
        pdf.setFont(font_regular, 10)
        pdf.drawString(10 * mm, y, "Invoice No")
        pdf.drawRightString(110 * mm, y, bill.invoice_no)
        
        y -= 6 * mm
        pdf.drawString(10 * mm, y, "Date")
        pdf.drawRightString(110 * mm, y, bill.billed_at.strftime('%d %b %Y'))
        
        y -= 6 * mm
        pdf.drawString(10 * mm, y, "Customer")
        pdf.drawRightString(110 * mm, y, bill.customer_name or 'Guest')
        
        y -= 8 * mm
        draw_dashed_line(y)
        
        y -= 6 * mm
        pdf.setFont(font_bold, 10)
        pdf.drawString(10 * mm, y, "Items")
        
        y -= 8 * mm
        pdf.setFont(font_bold, 8)
        pdf.setFillColor(colors.HexColor('#4A6076'))
        pdf.drawString(10 * mm, y, "ITEM")
        pdf.drawCentredString(65 * mm, y, "QTY")
        pdf.drawRightString(85 * mm, y, "PRICE")
        pdf.drawRightString(110 * mm, y, "AMOUNT")
        
        pdf.setFillColor(colors.black)
        
        y -= 6 * mm
        pdf.setFont(font_regular, 9)
        
        for order_item in bill.order.order_items:
            pdf.drawString(10 * mm, y, order_item.item.name)
            pdf.drawCentredString(65 * mm, y, str(order_item.quantity))
            pdf.drawRightString(85 * mm, y, f"₹{order_item.price:.2f}")
            pdf.drawRightString(110 * mm, y, f"₹{order_item.total_price:.2f}")
            y -= 6 * mm
            
        y -= 2 * mm
        draw_dashed_line(y)
        
        y -= 6 * mm
        pdf.drawString(10 * mm, y, "Subtotal")
        pdf.drawRightString(110 * mm, y, f"₹{bill.subtotal:.2f}")
        
        if bill.service_charge_amount and bill.service_charge_amount > 0:
            y -= 6 * mm
            pdf.drawString(10 * mm, y, f"Service Charge ({bill.service_charge_percent}%)")
            pdf.drawRightString(110 * mm, y, f"₹{bill.service_charge_amount:.2f}")
            
        if bill.cgst_amount and bill.cgst_amount > 0:
            y -= 6 * mm
            pdf.drawString(10 * mm, y, "CGST")
            pdf.drawRightString(110 * mm, y, f"₹{bill.cgst_amount:.2f}")
            
        if bill.sgst_amount and bill.sgst_amount > 0:
            y -= 6 * mm
            pdf.drawString(10 * mm, y, "SGST")
            pdf.drawRightString(110 * mm, y, f"₹{bill.sgst_amount:.2f}")
            
        if hasattr(bill, 'round_off_amount') and bill.round_off_amount != 0:
            y -= 6 * mm
            pdf.drawString(10 * mm, y, "Round Off")
            pdf.drawRightString(110 * mm, y, f"₹{bill.round_off_amount:.2f}")
            
        y -= 8 * mm
        draw_dashed_line(y)
        
        y -= 8 * mm
        pdf.setFont(font_bold, 11)
        pdf.setFillColor(colors.HexColor('#FF4500'))
        pdf.drawString(10 * mm, y, "Grand Total")
        pdf.drawRightString(110 * mm, y, f"₹{bill.grand_total:.2f}")
        pdf.setFillColor(colors.black)
        
        y -= 8 * mm
        draw_dashed_line(y)
        
        paid_amount = bill.paid_amount or 0.0
        due_amount = bill.due_amount or bill.grand_total
        
        y -= 8 * mm
        pdf.setFont(font_bold, 10)
        pdf.setFillColor(colors.HexColor('#008000'))
        pdf.drawString(10 * mm, y, "Paid")
        pdf.drawRightString(110 * mm, y, f"₹{paid_amount:.2f}")
        pdf.setFillColor(colors.black)
        
        y -= 6 * mm
        pdf.setFont(font_regular, 10)
        pdf.drawString(10 * mm, y, "Due")
        pdf.drawRightString(110 * mm, y, f"₹{due_amount:.2f}")
        
        y -= 8 * mm
        draw_dashed_line(y)
        
        y -= 10 * mm
        pdf.setFont(font_italic, 9)
        pdf.setFillColor(colors.grey)
        pdf.drawCentredString(60 * mm, y, bill.footer_message or "Thank you for dining with us!")
        
        pdf.save()