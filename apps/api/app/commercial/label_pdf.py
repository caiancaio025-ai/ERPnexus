from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from app.commercial.models import CommercialEquipment


def commercial_label_pdf(equipment: CommercialEquipment) -> bytes:
    """Etiqueta comercial/preventiva 40 x 40 mm com QR de 17 mm."""
    buffer = BytesIO()
    width = height = 40 * mm
    c = Canvas(buffer, pagesize=(width, height))
    c.setLineWidth(0.6)
    c.rect(1.2 * mm, 1.2 * mm, width - 2.4 * mm, height - 2.4 * mm)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(2.2 * mm, height - 5.5 * mm, "UNIVERSO")
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(width - 2.2 * mm, height - 5.5 * mm, equipment.serial_code or "---")
    c.line(2.2 * mm, height - 7 * mm, width - 2.2 * mm, height - 7 * mm)

    c.setFont("Helvetica-Bold", 6.6)
    c.drawString(2.2 * mm, height - 11 * mm, (equipment.equipment_type or "EQUIPAMENTO")[:31].upper())
    c.setFont("Helvetica", 5.8)
    specs = " · ".join(filter(None, [equipment.manufacturer, equipment.model]))[:44]
    c.drawString(2.2 * mm, height - 14 * mm, specs)
    details = " · ".join(filter(None, [equipment.power, equipment.voltage]))[:44]
    c.drawString(2.2 * mm, height - 17 * mm, details)

    c.setFillColor(colors.HexColor("#143653"))
    c.roundRect(2.2 * mm, 2.2 * mm, 15.5 * mm, 4 * mm, 1.2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 5.7)
    purpose = "PREVENTIVA" if equipment.purpose == "preventive" else "ALUGUEL / VENDA"
    c.drawCentredString(9.95 * mm, 3.25 * mm, purpose)
    c.setFillColor(colors.black)

    qr_value = f"COM-{equipment.serial_code or equipment.id}"
    widget = qr.QrCodeWidget(qr_value)
    widget.barLevel = "M"
    bounds = widget.getBounds()
    size = 17 * mm
    drawing = Drawing(
        size,
        size,
        transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0],
    )
    drawing.add(widget)
    renderPDF.draw(drawing, c, width - size - 2 * mm, 2.2 * mm)

    c.save()
    return buffer.getvalue()
