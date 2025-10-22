from io import BytesIO
from typing import List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from datetime import datetime

def _format_bool_tjanst(val: Any) -> str:
    if val is True:
        return "Tjänst"
    if val is False:
        return "Privat"
    return ""

def _page_fn(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    w, h = A4
    canvas.drawRightString(w - 15*mm, 10*mm, f"Sida {doc.page}")
    canvas.restoreState()

def _ym(datestr: str) -> str:
    # 'YYYY-MM' från 'YYYY-MM-DD'
    try:
        return datestr[:7]
    except Exception:
        return ""

def render_journal_pdf(rows: List[Dict[str, Any]]) -> bytes:
    """
    rows: list av dicts:
      - datum (YYYY-MM-DD)
      - start_odo, end_odo, km (float|str|None)
      - syfte (str|None)
      - tjanst (bool)
      - start_adress, slut_adress (str|None)
      - (valfritt) regnr (str), driver (str)
    """
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18*mm,
        bottomMargin=15*mm,
        leftMargin=15*mm,
        rightMargin=15*mm,
        title="Körjournal",
        author="Körjournal",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleSE", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=6))
    styles.add(ParagraphStyle(name="SubtitleSE", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.grey))
    styles.add(ParagraphStyle(name="Cell", fontName="Helvetica", fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="CellSmallGray", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey))
    styles.add(ParagraphStyle(name="SumCell", fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=1))  # center
    styles.add(ParagraphStyle(name="SumCellLeft", fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=0))  # left

    story = []

    # Titel + period
    story.append(Paragraph("Körjournal", styles["TitleSE"]))
    first_date = rows[0]["datum"] if rows else ""
    last_date  = rows[-1]["datum"] if rows else ""
    if rows:
        story.append(Paragraph(f"Period: {first_date} – {last_date}", styles["SubtitleSE"]))
    story.append(Spacer(1, 4*mm))

    # --- Tabellhuvud ---
    headers = [
        Paragraph("Datum", styles["Cell"]),
        Paragraph("Regnr", styles["Cell"]),
        Paragraph("Förare", styles["Cell"]),
        Paragraph("Mätarställning<br/>start", styles["Cell"]),
        Paragraph("Mätarställning<br/>slut", styles["Cell"]),
        Paragraph("Antal<br/>km", styles["Cell"]),
        Paragraph("Syfte", styles["Cell"]),
        Paragraph("Typ", styles["Cell"]),
    ]

    data = [headers]
    table_style_cmds = [
        ("FONT", (0,0), (-1,0), "Helvetica-Bold", 9),
        ("ALIGN", (0,0), (-1,0), "LEFT"),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EEEEEE")),
        ("LINEBELOW", (0,0), (-1,0), 0.75, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDDDDD")),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]

    # Kolumnbredder (mm) – total ~180mm
    # Datum 22, Regnr 16, Förare 24, Start 24, Slut 24, Km 16, Syfte 38 (≈ -1/3), Typ 16
    col_widths_mm = [22, 16, 24, 24, 24, 16, 38, 16]
    col_widths = [w * mm for w in col_widths_mm]

    # --- Rader + månadsgruppering ---
    total_km = 0.0
    month_km = 0.0
    prev_month = _ym(first_date) if rows else ""

    def add_month_sum(month_key: str):
        # Lägg in en helradig boxrad med månadsumma (inte knuten till Km-kolumn)
        nonlocal data, table_style_cmds, month_km
        if month_key and month_km is not None:
            row_idx = len(data)
            text = f"Summa {month_key} {round(month_km,1)} km"
            # en rad med 8 tomma celler
            data.append([""] * 8)
            # SPAN över hela raden och style som box
            table_style_cmds += [
                ("SPAN", (0, row_idx), (-1, row_idx)),
                ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#F3F3F3")),
                ("BOX", (0, row_idx), (-1, row_idx), 0.75, colors.HexColor("#BDBDBD")),
                ("ALIGN", (0, row_idx), (-1, row_idx), "CENTER"),
            ]
            data[row_idx][0] = Paragraph(text, styles["SumCell"])

    for r in rows:
        datum = r.get("datum", "") or ""
        month_key = _ym(datum)
        # byt månad? – lägg in föregående månads summa-rad
        if prev_month and month_key != prev_month:
            add_month_sum(prev_month)
            month_km = 0.0

        regnr = r.get("regnr", "") or ""
        driver = r.get("driver", "") or ""
        start_odo = r.get("start_odo", "")
        end_odo = r.get("end_odo", "")
        km_val = r.get("km", "")
        try:
            km_num = float(km_val) if km_val not in (None, "") else 0.0
        except Exception:
            km_num = 0.0
        total_km += km_num
        month_km += km_num

        syfte = r.get("syfte", "") or ""
        sa = r.get("start_adress") or ""
        ea = r.get("slut_adress") or ""
        # Syfte + (ev) adresser i samma cell i liten grå text → håller raden ihop
        syfte_lines = [syfte] if syfte else []
        small_lines = []
        if sa:
            small_lines.append(f"Start: {sa}")
        if ea:
            small_lines.append(f"Slut: {ea}")
        if small_lines:
            # append som <br/> + mindre grå
            syfte_html = (syfte + "<br/>" if syfte else "") + \
                         f'<font size="8" color="#888888">' + "<br/>".join(small_lines) + "</font>"
        else:
            syfte_html = syfte or ""

        row = [
            Paragraph(str(datum), styles["Cell"]),
            Paragraph(str(regnr), styles["Cell"]),
            Paragraph(str(driver), styles["Cell"]),
            Paragraph("" if start_odo is None else str(start_odo), styles["Cell"]),
            Paragraph("" if end_odo is None else str(end_odo), styles["Cell"]),
            Paragraph("" if km_val is None else str(km_val), styles["Cell"]),
            Paragraph(syfte_html, styles["Cell"]),
            Paragraph(_format_bool_tjanst(r.get("tjanst")), styles["Cell"]),
        ]
        data.append(row)
        prev_month = month_key

    # sista månadens summa
    if rows:
        add_month_sum(prev_month)

    # --- Tabell ---
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(table_style_cmds))

    story.append(tbl)
    story.append(Spacer(1, 6*mm))

    # --- Totalsumma i egen box, inte bunden till tabellens kolumner ---
    if rows:
        total_text = f'Perioden {first_date} – {last_date} — Totalt {round(total_km,1)} km'
        total_tbl = Table(
            [[Paragraph(total_text, styles["SumCellLeft"])]],
            colWidths=[sum(col_widths)]
        )
        total_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#EDEDED")),
            ("BOX", (0,0), (-1,-1), 1.0, colors.HexColor("#9E9E9E")),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(total_tbl)

    doc.build(story, onFirstPage=_page_fn, onLaterPages=_page_fn)
    pdf = buf.getvalue()
    buf.close()
    return pdf
