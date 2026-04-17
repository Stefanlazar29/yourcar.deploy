# -*- coding: utf-8 -*-
"""
Raport tehnic Mulberry — A4, structură grafică aliniată la factura „Boring Studios” (light):
antet [MULBERRY] + titlu dreapta, metadate pe două coloane, linie, tabel DESCRIPTION | QTY | UNIT | TOTAL,
secțiuni tehnice, zonă MULBERRYQR + cod QR, footer pe patru coloane.

Fără soft_score / scor de sănătate — acestea rămân doar în aplicație.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

WHITE = colors.white
BLACK = colors.black
LINE_W = 0.65


@dataclass
class MulberryTechnicalReportData:
    """Date raport tehnic — nicio valoare de tip soft score."""

    report_id: str = "MLRB-001"
    report_date: Optional[str] = None  # ex. "7 April 2026"; implicit azi
    subject_line: str = "Raport tehnic vehicul"
    vin: str = ""
    plate: str = ""
    mlbr_id: str = ""
    vehicle_label: str = ""  # ex. "Škoda Fabia · 2004"
    owner_label: str = ""  # ex. titular / flotă
    last_insurance: str = ""
    active_insurance: str = ""
    changes_made: str = ""
    last_issues: str = ""
    qr_url: str = ""  # URL encodat în MulberryQR (profil public / MulberryID)


def _qr_reader(payload: str, box_pt: float = 120) -> ImageReader:
    qr = qrcode.QRCode(version=None, box_size=4, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload or "https://mulberry.local")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _wrap_lines(c: canvas.Canvas, text: str, font: str, size: float, max_w: float) -> List[str]:
    if not (text or "").strip():
        return ["—"]
    lines_out: List[str] = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            lines_out.append("")
            continue
        words = block.split()
        cur: List[str] = []
        for w in words:
            trial = (" ".join(cur + [w])).strip()
            if c.stringWidth(trial, font, size) <= max_w:
                cur.append(w)
            else:
                if cur:
                    lines_out.append(" ".join(cur))
                cur = [w]
        if cur:
            lines_out.append(" ".join(cur))
    return lines_out if lines_out else ["—"]


def build_mulberry_technical_invoice_pdf(data: Optional[MulberryTechnicalReportData] = None) -> bytes:
    d = data or MulberryTechnicalReportData()
    rd = d.report_date or date.today().strftime("%d.%m.%Y")

    buf = io.BytesIO()
    w_pt, h_pt = A4
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFillColor(WHITE)
    c.rect(0, 0, w_pt, h_pt, stroke=0, fill=1)

    m = 18 * mm
    x0, x1 = m, w_pt - m
    cw = x1 - x0
    y = h_pt - m

    c.setFillColor(BLACK)
    c.setStrokeColor(BLACK)

    # ── Header: [MULBERRY] stânga, titlu dreapta (factură) ─────────────────
    brand = "[MULBERRY]"
    c.setFont("Helvetica-Bold", 20)
    c.drawString(x0, y - 7 * mm, brand)
    c.setFont("Helvetica-Bold", 11)
    right_lines = ["TECHNICAL", "REPORT"]
    ry = y - 5 * mm
    for i, ln in enumerate(right_lines):
        tw = c.stringWidth(ln, "Helvetica-Bold", 11)
        c.drawString(x1 - tw, ry - i * 13, ln)
    y -= 22 * mm

    # ── Metadate două coloane ───────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 9)
    left_meta = [f"[{rd}]", f"[{d.vehicle_label or 'Vehicle'}]"]
    if d.vin:
        left_meta.append(f"VIN [{d.vin}]")
    if d.plate:
        left_meta.append(f"PLATE [{d.plate}]")
    if d.owner_label:
        left_meta.append(f"[{d.owner_label}]")

    mid_x = x0 + cw * 0.48
    c.setFont("Helvetica-Bold", 9)
    yy = y
    for line in left_meta[:4]:
        c.drawString(x0, yy, line[:90])
        yy -= 11

    c.setFont("Helvetica-Bold", 9)
    rid = f"[#{d.report_id}]"
    tw = c.stringWidth(rid, "Helvetica-Bold", 9)
    c.drawString(x1 - tw, y, rid)
    subj = d.subject_line[:64] if d.subject_line else "—"
    if len(subj) > 48:
        subj = subj[:45] + "…"
    tw2 = c.stringWidth(f"[{subj}]", "Helvetica-Bold", 9)
    c.drawString(x1 - tw2, y - 11, f"[{subj}]")
    if d.mlbr_id:
        ml = f"MLBR [{d.mlbr_id}]"
        twm = c.stringWidth(ml, "Helvetica-Bold", 9)
        c.drawString(x1 - twm, y - 22, ml)

    y -= max(28 * mm, (len(left_meta) * 11) + 8 * mm)
    c.setLineWidth(LINE_W)
    c.line(x0, y, x1, y)
    y -= 10 * mm

    # ── Antet tabel ─────────────────────────────────────────────────────────
    col_desc = cw * 0.52
    col_q = cw * 0.14
    col_u = cw * 0.14
    col_t = cw * 0.20
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x0, y, "DESCRIPTION")
    c.drawString(x0 + col_desc, y, "QTY")
    c.drawString(x0 + col_desc + col_q, y, "UNIT")
    tw_tot = c.stringWidth("TOTAL", "Helvetica-Bold", 8)
    c.drawString(x1 - tw_tot, y, "TOTAL")
    y -= 4 * mm
    c.setLineWidth(0.35)
    c.line(x0, y, x1, y)
    y -= 8 * mm

    body_font = "Helvetica"
    body_size = 9
    title_size = 9
    dash = "—"

    def section_block(title: str, body: str) -> None:
        nonlocal y
        c.setFont("Helvetica-Bold", title_size)
        c.drawString(x0, y, title.upper())
        c.setFont(body_font, body_size)
        c.drawString(x0 + col_desc, y, dash)
        c.drawString(x0 + col_desc + col_q, y, dash)
        c.drawString(x0 + col_desc + col_q + col_u, y, dash)
        y -= 11
        max_txt_w = col_desc - 2 * mm
        for line in _wrap_lines(c, body, body_font, body_size, max_txt_w):
            c.setFont(body_font, body_size)
            c.drawString(x0 + 1 * mm, y, line or " ")
            y -= 10
        y -= 6 * mm

    section_block("Ultima asigurare", d.last_insurance)
    section_block("Asigurare activă", d.active_insurance)
    section_block("Schimbări efectuate", d.changes_made)
    section_block("Ultimele probleme detectate", d.last_issues)

    # Spațiu „respiră” ca pe factură
    y -= 18 * mm
    if y < 55 * mm:
        y = 55 * mm

    c.setLineWidth(LINE_W)
    c.line(x0, y, x1, y)
    y -= 8 * mm

    # ── Zonă MULBERRYQR (ca PAYMENT pe factură) ─────────────────────────────
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0, y - 2 * mm, "MULBERRYQR")
    qr_size = 34 * mm
    qr_x = x1 - qr_size - 2 * mm
    qr_ll_y = y - 10 * mm - qr_size
    try:
        ir = _qr_reader((d.qr_url or "https://mulberry.local").strip(), box_pt=qr_size)
        c.drawImage(ir, qr_x, qr_ll_y, width=qr_size, height=qr_size, mask="auto")
    except Exception:
        c.setFont("Helvetica", 8)
        c.drawString(qr_x, qr_ll_y + qr_size / 2, "[QR N/A]")

    c.setFont("Helvetica-Bold", 7)
    scan_w = c.stringWidth("SCAN QR · MULBERRYID", "Helvetica-Bold", 7)
    c.drawString(qr_x + (qr_size - scan_w) / 2, qr_ll_y - 4 * mm, "SCAN QR · MULBERRYID")

    c.setFont("Helvetica", 7.5)
    pay_txt = (
        "Scanare cod QR = acces la profilul public MulberryID asociat vehiculului. "
        "Nu include scoruri sau date sensibile din aplicație."
    )
    tx = x0
    ty = y - 10 * mm
    text_max_w = max(40 * mm, qr_x - x0 - 4 * mm)
    for part in pay_txt.split(". "):
        if not part:
            continue
        line = part.strip()
        if not line.endswith("."):
            line += "."
        for wl in _wrap_lines(c, line, "Helvetica", 7.5, text_max_w):
            c.drawString(tx, ty, wl)
            ty -= 9

    y = min(qr_ll_y - 8 * mm, ty - 4 * mm)
    c.setLineWidth(LINE_W)
    c.line(x0, y, x1, y)
    y -= 8 * mm

    # ── Footer patru coloane ─────────────────────────────────────────────────
    fw = cw / 4
    c.setFont("Helvetica-Bold", 7)
    foot = [
        ("MLBR", (d.mlbr_id or "—")[:28]),
        ("IDENTIFICATION", (d.vin or "—")[:24]),
        ("DOCUMENT", d.report_id[:24]),
        ("MULBERRY", "mulberry.local"),
    ]
    for i, (lab, val) in enumerate(foot):
        fx = x0 + i * fw
        c.drawString(fx, y, lab)
        c.setFont("Helvetica", 6.5)
        c.drawString(fx, y - 9, val)
        c.setFont("Helvetica-Bold", 7)

    c.showPage()
    c.save()
    out = buf.getvalue()
    buf.close()
    return out


def write_playerzero_report(path: str, data: Optional[MulberryTechnicalReportData] = None, **kwargs) -> None:
    from pathlib import Path

    Path(path).write_bytes(build_mulberry_technical_invoice_pdf(data))


if __name__ == "__main__":
    from pathlib import Path

    sample = MulberryTechnicalReportData(
        report_id="MLRB-TECH-001",
        subject_line="Extras tehnic identificare & istoric",
        vin="WVWZZZ1JZXW000001",
        plate="B 01 ABC",
        mlbr_id="MLBR-12-34-AB",
        vehicle_label="Škoda Fabia · 2004",
        owner_label="Flotă demo",
        last_insurance="Poliță RCA: Allianz · expiră 14.08.2025\nCASCO: nu este activă în sistem.",
        active_insurance="RCA activă până la 14.08.2025 · acoperire RO+UE",
        changes_made="Înlocuire filtru ulei (service autorizat) — 12.01.2026\nActualizare kilometraj în cloud.",
        last_issues="Cod P0420 înregistrat (istoric) — clarificat la service\nPresiune anvelope față dreapta sub prag (senzor)",
        qr_url="https://example.com/vehicle_present.html?m=MLBR-12-34-AB",
    )
    out = Path(__file__).resolve().parent.parent / "mulberry_technical_invoice_sample.pdf"
    write_playerzero_report(out, sample)
    print("Wrote", out, out.stat().st_size, "bytes")
