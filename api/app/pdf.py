from io import BytesIO
from typing import List, Dict, Any
from collections import defaultdict

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, LongTable
)


def _format_bool_tjanst(val):
    if val is True:
        return "Tjänst"
    if val is False:
        return "Privat"
    return ""


def _page_fn(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    w, h = A4
    canvas.drawRightString(w - 15 * mm, 10 * mm, f"Sida {doc.page}")
    canvas.restoreState()


def render_journal_pdf(rows: List[Dict[str, Any]]) -> bytes:
    """
    rows: lista av dicts (kronologiskt stigande i API):
      - datum (str 'YYYY-MM-DD')
      - start_odo (float|str|None)
      - end_odo   (float|str|None)
      - km        (float|str|None)
      - syfte     (str|None)
      - tjanst    (bool)
      - start_adress (str|None)
      - slut_adress  (str|None)
      - regnr (valfritt, om du skickar in det)
      - driver (valfritt, om du skickar in det)
    """
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        title="Körjournal",
        author="Körjournal",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleSE", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=6))
    styles.add(ParagraphStyle(name="SubtitleSE", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.grey))
    styles.add(ParagraphStyle(name="Cell", fontName="Helvetica", fontSize=9, leading=12, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="CellSmallGrey", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="MonthHeader", fontName="Helvetica-Bold", fontSize=12, leading=14, spaceBefore=6, spaceAfter=3))
    styles.add(ParagraphStyle(name="SumLabel", fontName="Helvetica-Bold", fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="SumValue", fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=2))  # right

    story = []

    # Titel + period (om data finns)
    story.append(Paragraph("Körjournal", styles["TitleSE"]))
    if rows:
        first = rows[0]["datum"]
        last = rows[-1]["datum"]
        story.append(Paragraph(f"Period: {first} – {last}", styles["SubtitleSE"]))
    story.append(Spacer(1, 4 * mm))

    # Grupp per månad (YYYY-MM)
    months = defaultdict(list)
    for r in rows:
        d = (r.get("datum") or "")[:7]  # 'YYYY-MM'
        months[d].append(r)

    # Kolumnrubriker
    headers = ["Datum", "Regnr", "Förare", "Mätarställning start", "Mätarställning slut", "Antal km", "Syfte"]

    # Kolumnbredder (i mm) – justerade: smal Regnr, Syfte -1/3
    # Summa bredd ≈ 180 mm (A4 minus marginaler)
    col_widths_mm = [22, 18, 24, 30, 30, 16, 40]  # Syfte kortare
    col_widths = [w * mm for w in col_widths_mm]

    grand_total = 0.0

    # Bygg en LongTable per månad
    for month in sorted(months.keys()):
        month_rows = months[month]

        # Månadshuvud
        story.append(Paragraph(f"Månad: {month}", styles["MonthHeader"]))

        data = [headers]

        month_total = 0.0

        for r in month_rows:
            datum = r.get("datum", "")
            regnr = r.get("regnr", "") or r.get("Regnr", "")  # om du skickar med i rows
            driver = r.get("driver", "") or r.get("Förare", "")
            start_odo = "" if r.get("start_odo") is None else str(r.get("start_odo"))
            end_odo = "" if r.get("end_odo") is None else str(r.get("end_odo"))
            km_val = r.get("km", "")
            km_str = "" if km_val is None else str(km_val)
            if isinstance(km_val, (int, float)):
                try:
                    month_total += float(km_val)
                except Exception:
                    pass

            syfte = r.get("syfte", "") or ""
            sa = r.get("start_adress") or ""
            ea = r.get("slut_adress") or ""

            # Lägg adresser i samma cell (mindre grå text)
            if sa or ea:
                syfte_html = f"{syfte}<br/><font size=8 color='grey'>"
                if sa:
                    syfte_html += f"Start: {sa}"
                if ea:
                    syfte_html += f"{'<br/>' if sa else ''}Slut: {ea}"
                syfte_html += "</font>"
            else:
                syfte_html = syfte

            row = [
                Paragraph(str(datum), styles["Cell"]),
                Paragraph(str(regnr), styles["Cell"]),
                Paragraph(str(driver), styles["Cell"]),
                Paragraph(start_odo, styles["Cell"]),
                Paragraph(end_odo, styles["Cell"]),
                Paragraph(km_str, styles["Cell"]),
                Paragraph(syfte_html, styles["Cell"]),
            ]
            data.append(row)

        # LongTable för månaden
        tbl = LongTable(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#CCCCCC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),

            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),

            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tbl)

        # Månadssumma – separat liten boxad tabell (två kolumner)
        sum_tbl = Table(
            [
                [Paragraph(f"Månadssumma {month}", styles["SumLabel"]),
                 Paragraph(f"{round(month_total, 1)} km", styles["SumValue"])]
            ],
            colWidths=[sum(col_widths[:-1]) - 10 * mm, col_widths[-1] + 10 * mm]  # ge lite extra utrymme åt värdet
        )
        sum_tbl.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#AAAAAA")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F7F7")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(Spacer(1, 2 * mm))
        story.append(sum_tbl)
        story.append(Spacer(1, 5 * mm))

        grand_total += month_total

    # Totalsumma i slutet
    if rows:
        first = rows[0]["datum"]
        last = rows[-1]["datum"]
        tot_tbl = Table(
            [
                [Paragraph(f"Period {first} – {last}", styles["SumLabel"]),
                 Paragraph(f"Totalt {round(grand_total, 1)} km", styles["SumValue"])]
            ],
            colWidths=[sum(col_widths[:-1]) - 10 * mm, col_widths[-1] + 10 * mm]
        )
        tot_tbl.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1.0, colors.black),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDEDED")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(Spacer(1, 4 * mm))
        story.append(tot_tbl)

    doc.build(story, onFirstPage=_page_fn, onLaterPages=_page_fn)
    pdf = buf.getvalue()
    buf.close()
    return pdf
