from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from app.commercial.models import CommercialEquipment


def _fit_text(value: str, font: str, font_size: float, max_width: float) -> str:
    """Limita o texto pela largura impressa, nao pela quantidade de caracteres."""
    text = " ".join(str(value or "").split())
    if stringWidth(text, font, font_size) <= max_width:
        return text
    while text and stringWidth(f"{text}...", font, font_size) > max_width:
        text = text[:-1]
    return f"{text.rstrip()}..." if text else "..."


def _location_lines(value: str, max_width: float) -> list[str]:
    """Exibe ate duas linhas de localizacao, sem invadir a area do QR Code."""
    font, size = "Helvetica", 5.8
    words = " ".join(str(value or "SEM LOCAL").split()).split(" ")
    lines: list[str] = []
    for word in words:
        candidate = f"{lines[-1]} {word}" if lines else word
        if not lines:
            lines.append(_fit_text(word, font, size, max_width))
        elif stringWidth(candidate, font, size) <= max_width:
            lines[-1] = candidate
        elif len(lines) == 1:
            lines.append(_fit_text(word, font, size, max_width))
        else:
            # A ultima linha recebe reticencias quando ha informacao nao exibida.
            lines[-1] = _fit_text(f"{lines[-1]}...", font, size, max_width)
            break
    return lines


def _rental_customer_lines(name: str, width: float) -> list[str]:
    """Distribui o nome do locatário em até duas linhas legíveis."""
    text = "CLIENTE: " + " ".join(str(name).split())
    font, size = "Helvetica-Bold", 5.6
    words = text.split()
    lines: list[str] = []
    for word in words:
        candidate = (lines[-1] + " " + word) if lines else word
        if not lines:
            lines.append(word)
        elif stringWidth(candidate, font, size) <= width:
            lines[-1] = candidate
        elif len(lines) == 1:
            lines.append(word)
        else:
            lines[-1] = _fit_text(" ".join([lines[-1], word]) + "...", font, size, width)
    return [_fit_text(line, font, size, width) for line in lines]


def commercial_label_pdf(equipment: CommercialEquipment, rental_customer_name: str | None = None) -> bytes:
    """Etiqueta de patrimonio 40 x 40 mm, sem sobreposicao de texto e QR."""
    buffer = BytesIO()
    width = height = 40 * mm
    c = Canvas(buffer, pagesize=(width, height))
    c.setLineWidth(0.6)
    c.rect(1.2 * mm, 1.2 * mm, width - 2.4 * mm, height - 2.4 * mm)

    patrimony = equipment.patrimony_code or f"PAT-{equipment.id:06d}"
    left = 2.2 * mm
    usable = width - 4.4 * mm

    # Empresa e codigo ficam em linhas diferentes, evitando sobreposicao.
    c.setFont("Helvetica-Bold", 7.8)
    c.drawString(left, 35.0 * mm, "UNIVERSO ELETRONICA")
    c.setFillColor(colors.HexColor("#143653"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(left, 30.8 * mm, _fit_text(patrimony, "Helvetica-Bold", 8.5, usable))
    c.setFillColor(colors.black)
    c.line(left, 28.8 * mm, width - left, 28.8 * mm)

    c.setFont("Helvetica-Bold", 6.6)
    c.drawString(
        left, 26.0 * mm,
        _fit_text((equipment.equipment_type or "EQUIPAMENTO").upper(), "Helvetica-Bold", 6.6, usable),
    )

    specs = " / ".join(filter(None, [equipment.manufacturer, equipment.model]))
    c.setFont("Helvetica", 5.8)
    c.drawString(left, 22.6 * mm, _fit_text(specs, "Helvetica", 5.8, usable))

    serial = f"S/N: {equipment.manufacturer_serial or '---'}"
    c.drawString(left, 19.3 * mm, _fit_text(serial, "Helvetica", 5.8, usable))

    # Abaixo do número de série, reservar coluna à esquerda do QR.
    qr_size = (12.4 if equipment.stock_status == "rented" and rental_customer_name else 16.2) * mm
    qr_x = width - qr_size - 2.2 * mm
    column_width = qr_x - left - 1.0 * mm
    if equipment.stock_status == "rented" and rental_customer_name:
        # Cliente somente da locação ativa, nunca de um orçamento antigo.
        c.setFillColor(colors.HexColor("#143653"))
        c.setFont("Helvetica-Bold", 5.6)
        for n, line in enumerate(_rental_customer_lines(rental_customer_name, usable)):
            c.drawString(left, (17.1 - 2.5 * n) * mm, line)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 5.6)
        c.drawString(left, 10.7 * mm, "LOCADO")
        c.setFont("Helvetica", 5.7)
        c.drawString(left, 7.8 * mm, _fit_text(equipment.location or "SEM LOCAL", "Helvetica", 5.7, column_width))
    else:
        c.setFont("Helvetica-Bold", 5.5)
        c.drawString(left, 16.1 * mm, "LOCAL:")
        c.setFont("Helvetica", 5.8)
        for n, line in enumerate(_location_lines(equipment.location or "SEM LOCAL", column_width)):
            c.drawString(left, (12.8 - n * 3.0) * mm, line)

    c.setFillColor(colors.HexColor("#143653"))
    c.roundRect(left, 2.2 * mm, 15.5 * mm, 4 * mm, 1.2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 5.6)
    c.drawCentredString(9.95 * mm, 3.25 * mm, "PATRIMONIO")
    c.setFillColor(colors.black)

    widget = qr.QrCodeWidget(patrimony)
    widget.barLevel = "M"
    bounds = widget.getBounds()
    drawing = Drawing(
        qr_size,
        qr_size,
        transform=[
            qr_size / (bounds[2] - bounds[0]), 0, 0,
            qr_size / (bounds[3] - bounds[1]), 0, 0,
        ],
    )
    drawing.add(widget)
    renderPDF.draw(drawing, c, qr_x, 2.2 * mm)

    c.save()
    return buffer.getvalue()
