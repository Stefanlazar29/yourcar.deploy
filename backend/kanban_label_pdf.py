# -*- coding: utf-8 -*-
"""
PDF etichetă industrială Kanban / e-ink — structură fixă după template „PERVASIVE DISPLAY”.
Chenare complete, secțiuni orizontale, Code128 + QR (reportlab + qrcode).

Notă MediaBox: pagina 76×172 mm produce în PDF aprox. [0 0 215.43 487.56] pt — este
formatul corect pentru etichetă îngustă (e-ink), nu A4. Rapoarte profesionale A4 în stil
minimal / factură tehnică A4: vezi ``mulberry_report_pdf.build_mulberry_technical_invoice_pdf``.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional, Union

import qrcode
from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

# ── Font CJK (fallback Helvetica dacă lipsește) ─────────────────────────────
CJK_NAME = "KanbanCJK"
CJK_BOLD_NAME = "KanbanCJKBd"
_CJK_READY = False


def _register_cjk_fonts() -> None:
    global _CJK_READY
    if _CJK_READY:
        return
    candidates = [
        Path(__file__).resolve().parent / "fonts" / "NotoSansSC-Regular.otf",
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyh.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    ]
    bold_candidates = [
        Path(__file__).resolve().parent / "fonts" / "NotoSansSC-Bold.otf",
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttf"),
    ]
    for p in candidates:
        if p.is_file():
            try:
                kw = {"subfontIndex": 0} if str(p).lower().endswith(".ttc") else {}
                pdfmetrics.registerFont(TTFont(CJK_NAME, str(p), **kw))
                _CJK_READY = True
                break
            except Exception:
                continue
    for p in bold_candidates:
        if p.is_file():
            try:
                kw = {"subfontIndex": 0} if str(p).lower().endswith(".ttc") else {}
                pdfmetrics.registerFont(TTFont(CJK_BOLD_NAME, str(p), **kw))
                break
            except Exception:
                continue


_register_cjk_fonts()


def _cjk() -> str:
    return CJK_NAME if _CJK_READY else "Helvetica"


def _cjkb() -> str:
    return CJK_BOLD_NAME if CJK_BOLD_NAME in pdfmetrics.getRegisteredFontNames() else _cjk()


@dataclass
class KanbanLabelData:
    """Câmpuri aliniate cu rândurile din etichetă (valori implicite = exemplul din design)."""

    header_title: str = "PERVASIVE DISPLAY"
    product_line: str = "Product Line 1"
    kanban_badge: str = "KANBAN"
    supply_label: str = "Supply source / Quelle"
    supply_value: str = "PWH-MSTK"
    demand_label: str = "Demand source / Senke"
    demand_value: str = "VERZ"
    material_label: str = "Material"
    material_code: str = "0906928"
    material_desc_label: str = "Materialdescription / Materialkurztext"
    material_description: str = "Bosch Polkern 1 263 104 811"
    size_label: str = "Size / Menge"
    size_value: str = "320'000"
    base_unit_label: str = "Base unit / Mengeneinheit"
    base_unit_value: str = "ST"
    shipping_label: str = "Shipping unit / Transporteinheit"
    ship_qty_1: str = "1"
    ship_qty_2: str = "14"
    barcode_ship_1: str = "1"
    barcode_ship_2: str = "14"
    printed_line: str = "Printed / Gedruckt: 02/08/2008"
    kanban_id_label: str = "Kanban ID:"
    kanban_id: str = "0906928C110022"
    qr_main_data: str = ""  # gol = kanban_id
    jp_header_left: str = "現品票"
    jp_company: str = "ABCD自動車(株)"
    grid1_l1: str = "當工順"
    grid1_v1: str = "1234567"
    grid1_l2: str = "次工順"
    grid1_v2: str = "1234567"
    grid1_l3: str = "生産方式"
    grid1_v3: str = "A B"
    grid2_l1: str = "要元"
    grid2_v1: str = "A"
    grid2_l2: str = "納入場所"
    grid2_v2: str = "12345678"
    grid2_l3: str = "納入指示日"
    grid2_v3: str = "MM/DD"
    grid2_l4: str = "納入時刻"
    grid2_v4: str = "HH : MM"
    part_section_title: str = "部品番号"
    part_long_number: str = "123456789012345678"
    part_center_id: str = "0906928C110022"
    xyz_part_label: str = "XYZ部品番号"
    barcode_large_value: str = "0906928C110022"
    ship_date_placeholder: str = "出荷指示日 MM/DD"
    ship_time_placeholder: str = "出荷時間 HH : MM"
    loc_placeholder: str = "LOC 12345"
    qty_contain_label: str = "収容数"
    qty_contain_value: str = "12345678"
    qty_order_label: str = "指示数"
    qty_order_value: str = "12345678"
    footer_barcode_value: str = "PWHMSTK"
    footer_human_readable: str = "P W H - M S T K"
    qr_footer_data: str = ""  # gol = kanban_id


def _make_qr_reader(payload: str, box_mm: float = 22) -> ImageReader:
    qr = qrcode.QRCode(version=None, box_size=3, border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _draw_hline(c: canvas.Canvas, x0: float, x1: float, y: float, w: float = 0.35) -> None:
    c.setLineWidth(w)
    c.setStrokeColor(colors.black)
    c.line(x0, y, x1, y)


def _draw_vline(c: canvas.Canvas, x: float, y0: float, y1: float, w: float = 0.35) -> None:
    c.setLineWidth(w)
    c.setStrokeColor(colors.black)
    c.line(x, y0, x, y1)


def _draw_arrow(c: canvas.Canvas, cx: float, cy: float, w: float = 4 * mm, h: float = 2 * mm) -> None:
    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)
    x0, y0 = cx - w / 2, cy - h / 2
    path = c.beginPath()
    path.moveTo(x0, cy)
    path.lineTo(x0 + w * 0.55, y0)
    path.lineTo(x0 + w * 0.55, cy - h * 0.25)
    path.lineTo(x0 + w, cy - h * 0.25)
    path.lineTo(x0 + w, cy + h * 0.25)
    path.lineTo(x0 + w * 0.55, cy + h * 0.25)
    path.lineTo(x0 + w * 0.55, y0 + h)
    path.close()
    c.drawPath(path, stroke=0, fill=1)


def _text_block(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    w: float,
    label: str,
    value: str,
    *,
    label_pt: float = 5.2,
    value_pt: float = 8.5,
    label_font: str = "Helvetica",
    value_font: str = "Helvetica-Bold",
    pad: float = 0.8 * mm,
) -> None:
    c.setFillColor(colors.black)
    yy = y_top - pad - label_pt * 0.35
    c.setFont(label_font, label_pt)
    c.drawString(x + pad, yy, label)
    c.setFont(value_font, value_pt)
    c.drawString(x + pad, yy - value_pt * 1.15 - 0.5 * mm, value)


def _text_center(c: canvas.Canvas, y_baseline: float, text: str, font: str, size: float, x0: float, x1: float) -> None:
    c.setFont(font, size)
    tw = c.stringWidth(text, font, size)
    cx = (x0 + x1) / 2 - tw / 2
    c.drawString(cx, y_baseline, text)


def build_kanban_label_pdf(
    data: Optional[KanbanLabelData] = None,
    *,
    page_w_mm: float = 76,
    # Înălțime = margin*2 + suma rândurilor (etichetă compactă, fără bandă goală jos).
    page_h_mm: float = 172.0,
    margin_mm: float = 1.2,
) -> bytes:
    """
    Generează PDF-ul etichetei; returnează bytes (structură fixă 100% după template).
    """
    d = data or KanbanLabelData()
    qr_main = d.qr_main_data or d.kanban_id
    qr_foot = d.qr_footer_data or d.kanban_id

    buf = io.BytesIO()
    pw = page_w_mm * mm
    ph = page_h_mm * mm
    m = margin_mm * mm
    c = canvas.Canvas(buf, pagesize=(pw, ph))

    # Fundal e-ink (gri deschis, contrast ridicat cu text/chenar negru)
    eink_bg = colors.HexColor("#d2d2d2")
    c.setFillColor(eink_bg)
    c.rect(0, 0, pw, ph, stroke=0, fill=1)

    x0, x1 = m, pw - m
    W = x1 - x0

    # Înălțimi rânduri (mm) — suma ≈ page_h_mm - 2*margin_mm
    h1 = 9.0   # PERVASIVE DISPLAY
    h2 = 6.2   # Product Line | KANBAN
    h3 = 11.0  # Supply → Demand
    h4 = 11.0  # Material
    h5a = 26.0  # QR + cantități + coduri
    h5b = 5.5   # Printed / Kanban ID
    h6 = 8.0   # 現品票
    h7 = 9.0   # grid 3
    h8 = 9.0   # grid 4
    h9 = 7.5   # 部品番号 + număr lung
    h10 = 6.0  # ID centrat
    h11 = 18.0  # XYZ + Code128 lat (aproape tot rândul)
    h12 = 7.2  # 3 coloane
    h13 = 7.2  # 2 coloane
    h14 = 19.0  # footer barcode + QR

    y = ph - m  # margine sus (y mare)

    def row_top(h: float) -> tuple[float, float]:
        nonlocal y
        y_top = y
        y_bot = y - h * mm
        y = y_bot
        return y_top, y_bot

    # Chenar exterior
    c.setLineWidth(0.6)
    c.rect(x0, m, W, ph - 2 * m, stroke=1, fill=0)

    # ── Rând 1: titlu principal ─────────────────────────────────────────────
    yt, yb = row_top(h1)
    _draw_hline(c, x0, x1, yt)
    _draw_hline(c, x0, x1, yb)
    _draw_vline(c, x0, yb, yt)
    _draw_vline(c, x1, yb, yt)
    c.setFont("Helvetica-Bold", 11.5)
    c.setFillColor(colors.black)
    title = d.header_title
    tw = c.stringWidth(title, "Helvetica-Bold", 11.5)
    c.drawString((x0 + x1) / 2 - tw / 2, yb + (h1 * mm) / 2 - 3.2 * mm, title)

    # ── Rând 2: Product Line 1 | KANBAN ─────────────────────────────────────
    yt, yb = row_top(h2)
    _draw_hline(c, x0, x1, yb)
    xm = (x0 + x1) / 2
    _draw_vline(c, xm, yb, yt)
    c.setFont("Helvetica-Bold", 7.8)
    c.drawString(x0 + 1.2 * mm, yb + 1.8 * mm, d.product_line)
    twk = c.stringWidth(d.kanban_badge, "Helvetica-Bold", 7.8)
    c.drawString(x1 - twk - 1.2 * mm, yb + 1.8 * mm, d.kanban_badge)

    # ── Rând 3: Supply | → | Demand ─────────────────────────────────────────
    yt, yb = row_top(h3)
    _draw_hline(c, x0, x1, yb)
    x_sp = x0 + W * 0.38
    x_sd = x0 + W * 0.50
    _draw_vline(c, x_sp, yb, yt)
    _draw_vline(c, x_sd, yb, yt)
    _text_block(c, x0, yt, x_sp - x0, d.supply_label, d.supply_value, label_pt=5.0, value_pt=9.0)
    _text_block(c, x_sd, yt, x1 - x_sd, d.demand_label, d.demand_value, label_pt=5.0, value_pt=9.0)
    _draw_arrow(c, (x_sp + x_sd) / 2, yb + h3 * mm / 2, w=5 * mm, h=2.4 * mm)

    # ── Rând 4: Material 30% | descriere 70% ────────────────────────────────
    yt, yb = row_top(h4)
    _draw_hline(c, x0, x1, yb)
    x_split = x0 + W * 0.30
    _draw_vline(c, x_split, yb, yt)
    _text_block(c, x0, yt, x_split - x0, d.material_label, d.material_code, label_pt=5.0, value_pt=9.5)
    _text_block(
        c,
        x_split,
        yt,
        x1 - x_split,
        d.material_desc_label,
        d.material_description,
        label_pt=5.0,
        value_pt=7.8,
    )

    # ── Rând 5a: QR | Size/Base | Shipping | Code128 dreapta ─────────────────
    yt, yb = row_top(h5a)
    _draw_hline(c, x0, x1, yb)
    qr_w = 21 * mm
    bar_r = 19 * mm
    mid_total = W - qr_w - bar_r
    mid_l = mid_total * 0.48
    mid_r = mid_total - mid_l
    x_qr_end = x0 + qr_w
    x_mid_split = x_qr_end + mid_l
    x_bar_start = x1 - bar_r
    _draw_vline(c, x_qr_end, yb, yt)
    _draw_vline(c, x_mid_split, yb, yt)
    _draw_vline(c, x_bar_start, yb, yt)

    # QR stânga
    ir = _make_qr_reader(qr_main, qr_w)
    c.drawImage(ir, x0 + 0.8 * mm, yb + 1 * mm, width=qr_w - 1.6 * mm, height=qr_w - 1.6 * mm, mask="auto")

    # Mijloc stânga: Size (sus) + Base (jos) — împarte vertical pe mid_l
    y_mid_top = yt - 0.5 * mm
    h_half = (h5a * mm) * 0.48
    _draw_hline(c, x_qr_end, x_mid_split, y_mid_top - h_half, 0.3)
    _text_block(
        c,
        x_qr_end,
        y_mid_top,
        mid_l,
        d.size_label,
        d.size_value,
        label_pt=4.8,
        value_pt=8.5,
        pad=0.6 * mm,
    )
    _text_block(
        c,
        x_qr_end,
        y_mid_top - h_half - 0.5 * mm,
        mid_l,
        d.base_unit_label,
        d.base_unit_value,
        label_pt=4.8,
        value_pt=8.5,
        pad=0.6 * mm,
    )

    # Mijloc dreapta: Shipping + 1x [bar] / 14x [bar]
    ship_y_top = yt - 0.8 * mm
    c.setFont("Helvetica", 4.8)
    c.drawString(x_mid_split + 0.6 * mm, ship_y_top - 4.5 * mm, d.shipping_label)
    row1_y = ship_y_top - 9 * mm
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x_mid_split + 0.6 * mm, row1_y, d.ship_qty_1 + " x")
    bc1 = Code128(d.barcode_ship_1, barHeight=5.5 * mm, barWidth=0.18 * mm)
    bc1.drawOn(c, x_mid_split + 8 * mm, row1_y - 1 * mm)
    row2_y = row1_y - 8 * mm
    c.drawString(x_mid_split + 0.6 * mm, row2_y, d.ship_qty_2 + " x")
    bc2 = Code128(d.barcode_ship_2, barHeight=5.5 * mm, barWidth=0.18 * mm)
    bc2.drawOn(c, x_mid_split + 8 * mm, row2_y - 1 * mm)

    # Barcode vertical dreapta (centrat pe coloană)
    bc_side = Code128(d.kanban_id, barHeight=7.5 * mm, barWidth=0.2 * mm)
    bx = x_bar_start + (bar_r - bc_side.width) / 2 if hasattr(bc_side, "width") else x_bar_start + 2 * mm
    try:
        bw = bc_side.width
    except Exception:
        bw = bar_r - 4 * mm
        bx = x_bar_start + (bar_r - bw) / 2
    bc_side.drawOn(c, bx, yb + (h5a * mm - bc_side.height) / 2)

    # ── Rând 5b: Printed | Kanban ID ─────────────────────────────────────────
    yt, yb = row_top(h5b)
    _draw_hline(c, x0, x1, yb)
    _draw_vline(c, x0, yb, yt)
    _draw_vline(c, x1, yb, yt)
    xm = (x0 + x1) / 2
    _draw_vline(c, xm, yb, yt)
    c.setFont("Helvetica", 5.0)
    c.drawString(x0 + 1 * mm, yb + 1.2 * mm, d.printed_line)
    kid = f"{d.kanban_id_label} {d.kanban_id}"
    tw = c.stringWidth(kid, "Helvetica", 5.0)
    c.drawString(x1 - tw - 1 * mm, yb + 1.2 * mm, kid)

    # ── Rând 6: 現品票 | companie (separator gros = jumătatea EN/DE vs JP) ───
    yt, yb = row_top(h6)
    _draw_hline(c, x0, x1, yt, w=1.05)
    _draw_hline(c, x0, x1, yb)
    xm = x0 + W * 0.42
    _draw_vline(c, xm, yb, yt)
    c.setFont(_cjkb(), 11)
    c.drawString(x0 + 1 * mm, yb + 2.2 * mm, d.jp_header_left)
    c.setFont(_cjk(), 8.5)
    twc = c.stringWidth(d.jp_company, _cjk(), 8.5)
    c.drawString(x1 - twc - 1 * mm, yb + 2.5 * mm, d.jp_company)

    # ── Rând 7: grid 3 coloane ────────────────────────────────────────────────
    yt, yb = row_top(h7)
    _draw_hline(c, x0, x1, yb)
    g = W / 3
    _draw_vline(c, x0 + g, yb, yt)
    _draw_vline(c, x0 + 2 * g, yb, yt)
    _text_block(c, x0, yt, g, d.grid1_l1, d.grid1_v1, label_font=_cjk(), value_font=_cjkb(), label_pt=5, value_pt=8)
    _text_block(
        c, x0 + g, yt, g, d.grid1_l2, d.grid1_v2, label_font=_cjk(), value_font=_cjkb(), label_pt=5, value_pt=8
    )
    _text_block(
        c,
        x0 + 2 * g,
        yt,
        g,
        d.grid1_l3,
        d.grid1_v3,
        label_font=_cjk(),
        value_font=_cjkb(),
        label_pt=5,
        value_pt=8,
    )

    # ── Rând 8: grid 4 coloane ─────────────────────────────────────────────────
    yt, yb = row_top(h8)
    _draw_hline(c, x0, x1, yb)
    g4 = W / 4
    for i in range(1, 4):
        _draw_vline(c, x0 + i * g4, yb, yt)
    pairs = [
        (d.grid2_l1, d.grid2_v1),
        (d.grid2_l2, d.grid2_v2),
        (d.grid2_l3, d.grid2_v3),
        (d.grid2_l4, d.grid2_v4),
    ]
    for i, (lb, vl) in enumerate(pairs):
        _text_block(
            c,
            x0 + i * g4,
            yt,
            g4,
            lb,
            vl,
            label_font=_cjk(),
            value_font=_cjkb(),
            label_pt=4.6,
            value_pt=7.2,
        )

    # ── Rând 9: 部品番号 + număr lung ─────────────────────────────────────────
    yt, yb = row_top(h9)
    _draw_hline(c, x0, x1, yb)
    c.setFont(_cjk(), 7.5)
    c.drawString(x0 + 1 * mm, yb + 2.8 * mm, d.part_section_title)
    c.setFont(_cjkb(), 8.5)
    c.drawString(x0 + 16 * mm, yb + 2.5 * mm, d.part_long_number)

    # ── Rând 10: ID centrat ───────────────────────────────────────────────────
    yt, yb = row_top(h10)
    _draw_hline(c, x0, x1, yb)
    c.setFont("Helvetica-Bold", 7.5)
    _text_center(c, yb + 2.0 * mm, d.part_center_id, "Helvetica-Bold", 7.5, x0, x1)

    # ── Rând 11: XYZ部品番号 + Code128 foarte lat (ca pe etichetă fizică) ─────
    yt, yb = row_top(h11)
    _draw_hline(c, x0, x1, yb)
    c.setFillColor(colors.black)
    c.setFont(_cjk(), 6.8)
    c.drawString(x0 + 1 * mm, yb + h11 * mm - 4.2 * mm, d.xyz_part_label)
    max_bar_w = W - 4 * mm
    bar_h = min(10.5 * mm, h11 * mm - 7 * mm)
    bw = 0.28 * mm
    bc_big = Code128(d.barcode_large_value, barHeight=bar_h, barWidth=bw)
    while getattr(bc_big, "width", max_bar_w + 1) > max_bar_w and bw > 0.11 * mm:
        bw -= 0.015 * mm
        bc_big = Code128(d.barcode_large_value, barHeight=bar_h, barWidth=bw)
    bx2 = x0 + (W - bc_big.width) / 2
    bc_big.drawOn(c, bx2, yb + 2 * mm)

    # ── Rând 12: 3 coloane placeholder ────────────────────────────────────────
    yt, yb = row_top(h12)
    _draw_hline(c, x0, x1, yb)
    g3 = W / 3
    _draw_vline(c, x0 + g3, yb, yt)
    _draw_vline(c, x0 + 2 * g3, yb, yt)
    c.setFont(_cjk(), 5.8)
    c.drawString(x0 + 0.8 * mm, yb + 1.8 * mm, d.ship_date_placeholder)
    c.drawString(x0 + g3 + 0.8 * mm, yb + 1.8 * mm, d.ship_time_placeholder)
    c.drawString(x0 + 2 * g3 + 0.8 * mm, yb + 1.8 * mm, d.loc_placeholder)

    # ── Rând 13: 収容数 | 指示数 ─────────────────────────────────────────────
    yt, yb = row_top(h13)
    _draw_hline(c, x0, x1, yb)
    xm = (x0 + x1) / 2
    _draw_vline(c, xm, yb, yt)
    c.setFont(_cjk(), 6.5)
    left_txt = f"{d.qty_contain_label} {d.qty_contain_value}"
    right_txt = f"{d.qty_order_label} {d.qty_order_value}"
    c.drawString(x0 + 1 * mm, yb + 2 * mm, left_txt)
    c.drawString(xm + 1 * mm, yb + 2 * mm, right_txt)

    # ── Rând 14: footer Code128 lat + QR ─────────────────────────────────────
    yt, yb = row_top(h14)
    _draw_hline(c, x0, x1, yb)
    foot_split = x0 + W * 0.74
    _draw_vline(c, foot_split, yb, yt)
    bc_f = Code128(d.footer_barcode_value, barHeight=8 * mm, barWidth=0.24 * mm)
    max_bw = foot_split - x0 - 4 * mm
    bx0 = x0 + 2 * mm
    if bc_f.width > max_bw:
        bc_f = Code128(d.footer_barcode_value, barHeight=7 * mm, barWidth=0.18 * mm)
    bc_f.drawOn(c, bx0, yb + 8 * mm)
    c.setFont("Helvetica-Bold", 6.5)
    spaced = d.footer_human_readable
    tws = c.stringWidth(spaced, "Helvetica-Bold", 6.5)
    c.drawString(x0 + (foot_split - x0 - tws) / 2, yb + 2 * mm, spaced)
    irf = _make_qr_reader(qr_foot, 18)
    qs = 17 * mm
    c.drawImage(irf, x1 - qs - 1.5 * mm, yb + 1 * mm, width=qs, height=qs, mask="auto")

    c.showPage()
    c.save()
    out = buf.getvalue()
    buf.close()
    return out


def write_kanban_label_pdf(path: Union[str, Path], data: Optional[KanbanLabelData] = None) -> None:
    Path(path).write_bytes(build_kanban_label_pdf(data))


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "kanban_pervasive_sample.pdf"
    write_kanban_label_pdf(out)
    print("Wrote", out, "size", out.stat().st_size)
