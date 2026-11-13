"""Etiqueta de estoque com layout mais legível, QR e hierarquia visual."""
from io import BytesIO
from textwrap import wrap

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

WIDTH = 50 * mm
HEIGHT = 35 * mm
PADDING = 2 * mm


def _crop(value: str, size: float, width: float) -> str:
    text = " ".join(str(value or "").split())
    while text and stringWidth(text, "Helvetica", size) > width:
        text = text[:-1]
    return text


def _lines(value: str, size: float, width: float, limit: int) -> list[str]:
    raw = " ".join(str(value or "").split())
    pieces = wrap(raw, width=28) if raw else [""]
    lines: list[str] = []
    for piece in pieces:
        candidate = _crop(piece, size, width)
        if candidate:
            lines.append(candidate)
        if len(lines) >= limit:
            break
    return lines or [""]


def inventory_label_pdf(*, stock_code: str, name: str, serial: str | None, location: str) -> bytes:
    target = BytesIO()
    c = Canvas(target, pagesize=(WIDTH, HEIGHT))

    c.setStrokeColor(colors.HexColor("#1f4f6b"))
    c.setLineWidth(0.7)
    c.roundRect(0.9 * mm, 0.9 * mm, WIDTH - 1.8 * mm, HEIGHT - 1.8 * mm, 2 * mm, stroke=1, fill=0)

    c.setFillColor(colors.HexColor("#eaf5fb"))
    c.roundRect(1.4 * mm, HEIGHT - 8.8 * mm, WIDTH - 2.8 * mm, 6.6 * mm, 1.8 * mm, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#17445f"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(3 * mm, HEIGHT - 5.9 * mm, "ESTOQUE • UNIVERSO")

    c.setFillColor(colors.HexColor("#0e2a3f"))
    c.setFont("Helvetica-Bold", 9.6)
    c.drawString(3 * mm, HEIGHT - 12.2 * mm, _crop(stock_code[:24], 9.6, 27 * mm))

    c.setFont("Helvetica-Bold", 6.3)
    c.drawString(3 * mm, HEIGHT - 16.8 * mm, "ITEM")
    c.setFont("Helvetica", 6.1)
    name_top = HEIGHT - 19.7 * mm
    for idx, line in enumerate(_lines(name, 6.1, 27 * mm, 2)):
        c.drawString(3 * mm, name_top - (idx * 3.2 * mm), line)

    c.setFont("Helvetica-Bold", 6.1)
    c.drawString(3 * mm, 9.6 * mm, "SÉRIE / LOTE")
    c.setFont("Helvetica", 5.8)
    c.drawString(3 * mm, 7.0 * mm, _crop(serial or "Controle por quantidade", 5.8, 27 * mm))

    c.setFont("Helvetica-Bold", 6.1)
    c.drawString(3 * mm, 4.4 * mm, "LOCAL")
    c.setFont("Helvetica", 5.8)
    c.drawString(3 * mm, 1.8 * mm, _crop(location, 5.8, 27 * mm))

    widget = QrCodeWidget(stock_code)
    bounds = widget.getBounds()
    side = 15 * mm
    drawing = Drawing(
        side,
        side,
        transform=[side / (bounds[2] - bounds[0]), 0, 0, side / (bounds[3] - bounds[1]), 0, 0],
    )
    drawing.add(widget)
    renderPDF.draw(drawing, c, WIDTH - side - 3.2 * mm, 8.3 * mm)

    c.setFont("Helvetica", 4.9)
    c.setFillColor(colors.HexColor("#46667b"))
    c.drawCentredString(WIDTH - (side / 2) - 3.2 * mm, 5.2 * mm, "QR para localizar")

    c.save()
    return target.getvalue()
