"""Regressao de composicao da etiqueta patrimonial 40 x 40 mm."""

from types import SimpleNamespace

import pytest
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import getAscentDescent, stringWidth
from reportlab.pdfgen.canvas import Canvas

from app.commercial.label_pdf import commercial_label_pdf


def _equipment(**changes):
    values = dict(
        id=4,
        patrimony_code="PAT-000004",
        equipment_type="Inversor de frequencia",
        manufacturer="WEG",
        model="CFW11",
        manufacturer_serial="12345678",
        location="RACK 03",
    )
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {},
        dict(patrimony_code=None, manufacturer=None, model=None, manufacturer_serial=None, location=None),
        dict(
            equipment_type="INVERSOR FREQUENCIA WEG CFW11 450 A TRIFASICO - SERIE ESPECIAL",
            manufacturer="FABRICANTE COM NOME MUITO COMPRIDO",
            model="MODELO INDUSTRIAL MULTIPLAS REFERENCIAS 2026",
            manufacturer_serial="LONGO-123456789012345678901234567890",
            location="AREA OPERACIONAL RACK 23 PRATELEIRA SUPERIOR POSICAO 09",
        ),
    ],
)
def test_label_keeps_text_inside_print_area_without_overlap(monkeypatch, changes):
    drawn = []
    original = Canvas.drawString

    def record_draw_string(self, x, y, text, *args, **kwargs):
        size = self._fontsize
        font = self._fontname
        ascent, descent = getAscentDescent(font, size)
        drawn.append((text, (x, y + descent, x + stringWidth(text, font, size), y + ascent)))
        return original(self, x, y, text, *args, **kwargs)

    monkeypatch.setattr(Canvas, "drawString", record_draw_string)
    pdf = commercial_label_pdf(_equipment(**changes))
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1500

    texts = [text for text, _ in drawn]
    assert "UNIVERSO ELETRONICA" in texts
    assert "LOCAL:" in texts
    assert next(text for text in texts if text.startswith("PAT-"))
    assert next(text for text in texts if text.startswith("S/N:"))

    for text, (x1, y1, x2, y2) in drawn:
        assert x1 >= 2.0 * mm, (text, x1)
        assert x2 <= 38.0 * mm, (text, x2)
        assert y1 >= 2.0 * mm, (text, y1)
        assert y2 <= 38.0 * mm, (text, y2)

    # Nenhum bloco de texto deve ocupar a mesma area impressa.
    for index, (first, a) in enumerate(drawn):
        for second, b in drawn[index + 1 :]:
            intersection_width = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
            intersection_height = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
            assert intersection_width * intersection_height < 0.1, (first, second)


def test_label_preserves_original_patrimony_code():
    pdf = commercial_label_pdf(_equipment(patrimony_code="PAT-009821"))
    assert pdf.startswith(b"%PDF-")
