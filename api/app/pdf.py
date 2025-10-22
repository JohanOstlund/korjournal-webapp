from io import BytesIO
from typing import List, Dict, Any, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)

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

def _month_key(yyyy_mm_dd: str) -> str:
    # yyyy-mm
    return (yyyy_mm_dd or "")[:7]

def _sum_km(rows: List[Dict[str, Any]]) -> float:
    s = 0.0
    for r in rows:
        try:
            v = r.get("km", None)
            if v is None or v == "":
                continue
            s += float(v)
        except Exception:
            pass
    return round(s, 1)

def render_journal_pdf(rows: List[Dict[str, Any]]) -> bytes:
    """
    rows: lista av dicts (redan sorterade stigande datum) med nycklar:
      - datum (str 'YYYY-MM-DD')
      - start_odo, end_odo, km
      - syfte (str|None)
      - tjanst (bool)
      - start_adress, slut_adress (valfritt)
      - (valfritt) vehicle_reg, driver_name om du vill visa i header
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
    styles.add(ParagraphStyle(name="CellSmall", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey))
    styles.add(ParagraphStyle(name="SumLeft", fontName="Helvetica-Bold", fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="SumRight", fontName="Helvetica-Bold", fontSize=9, leading=12, alignment=2))  # right
    styles.add(ParagraphStyle(name="GrandTitle", fontName="Helvetica-Bold", fontSize=10, leading=13))
    styles.add(ParagraphStyle(name="GrandVal", fontName="Helvetica-Bold", fontSize=10, leading=13, alignment=2))

    story = []

    # Titel + period
    story.append(Paragraph("Körjournal", styles["TitleSE"]))
    if rows:
        first = rows[0]["datum"]
        last = rows[-1]["datum"]
        story.append(Paragraph(f"Period: {first} – {last}", styles["SubtitleSE"]))
    story.append(Spacer(1, 4*mm))

    # Huvudtabell
    # Kolumnbredder (ca 180 mm yta): Datum 22, Regnr 16, Förare 28, Startodo 26, Slutodo 26, Km 18, Syfte 44
    col_widths_mm = [22, 16, 28, 26, 26, 18, 44]
    col_widths = [w * mm for w in col_widths_mm]

    headers = ["Datum", "Regnr", "Förare", "Mätarställning start", "Mätarställning slut", "Km", "Syfte"]
    table_data: List[List[Any]] = [headers]

    # gruppera per månad
    current_month = None
    month_rows: List[Dict[str, Any]] = []
    grand_rows: List[Dict[str, Any]] = []

    def _append_trip_row(r: Dict[str, Any]):
        # Skapa rad + ev. adresserad
        syfte_p = Paragraph(str(r.get("syfte", "") or ""), styles["Cell"])
        row = [
            Paragraph(str(r.get("datum", "")), styles["Cell"]),
            Paragraph(str(r.get("vehicle_reg", "")), styles["Cell"]),
            Paragraph(str(r.get("driver_name", "")), styles["Cell"]),
            Paragraph("" if r.get("start_odo") in (None, "") else str(r.get("start_odo")), styles["Cell"]),
            Paragraph("" if r.get("end_odo") in (None, "") else str(r.get("end_odo")), styles["Cell"]),
            Paragraph("" if r.get("km") in (None, "") else str(r.get("km")), styles["Cell"]),
            syfte_p,
        ]
        table_data.append(row)

        # adresser på en egen "under-rad"
        sa = r.get("start_adress") or ""
        ea = r.get("slut_adress") or ""
        if sa or ea:
            addr_txt = []
            if sa: addr_txt.append(f"Start: {sa}")
            if ea: addr_txt.append(f"Slut: {ea}")
            # lägg adresserna i syfte-kolumnen – övriga tomma
            table_data.append([
                Paragraph("", styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
                Paragraph("<br/>".join(addr_txt), styles["CellSmall"]),
            ])

    def _month_sum_block(month_key: str, month_items: List[Dict[str, Any]]):
        # Skapa en 2-kolumners sammanfattning, vänster "Månadssumma YYYY-MM", höger "NNN km"
        s = _sum_km(month_items)
        left = Paragraph(f"Månadssumma {month_key}", styles["SumLeft"])
        right = Paragraph(f"{s} km", styles["SumRight"])
        box = Table([[left, right]], colWidths=[sum(col_widths[:-1]), col_widths[-1]])
        box.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.75, colors.HexColor("#999999")),
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#F5F5F5")),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        # Lägg som en hel rad i tabellen via KeepTogether + en "spalt-överbryggning" med 2-kolumners tabell
        return box

    # Bygg data med månadsblock
    for r in rows:
        mk = _month_key(r.get("datum", ""))
        if current_month is None:
            current_month = mk

        if mk != current_month:
            # injicera månadssumma-rad (egen tabell) – vi lägger in som en separat tabellrad via en "spanned" cell
            # Vi gör det som en rad i tabellen: 7 kolumner -> lägg en cell som spänner över alla kolumner
            sum_box = _month_sum_block(current_month, month_rows)
            table_data.append([KeepTogether(sum_box)] + ["" for _ in range(len(headers)-1)])
            month_rows = []
            current_month = mk

        # Append resa
        _append_trip_row(r)
        month_rows.append(r)
        grand_rows.append(r)

    # sista månadens summa
    if current_month is not None:
        sum_box = _month_sum_block(current_month, month_rows)
        table_data.append([KeepTogether(sum_box)] + ["" for _ in range(len(headers)-1)])

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONT", (0,0), (-1,0), "Helvetica-Bold", 9),
        ("ALIGN", (0,0), (-1,0), "LEFT"),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EEEEEE")),
        ("LINEBELOW", (0,0), (-1,0), 0.75, colors.HexColor("#CCCCCC")),

        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#DDDDDD")),

        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),

        # Sammanfattningsraden (sum_box) spänner över alla kolumner:
        ("SPAN", (0, -1), (-1, -1)),  # säkerhetsnät om sista raden är box
    ]))

    # Förhindra att en resa delas över sidor: vi lägger hela tabellen i story,
    # men adresser ligger direkt under huvudraden så de bryts inte isär i denna struktur.
    story.append(tbl)

    # Grand total i slutet
    story.append(Spacer(1, 6*mm))
    total_km = _sum_km(grand_rows)
    first_date = rows[0]["datum"] if rows else ""
    last_date = rows[-1]["datum"] if rows else ""
    grand = Table(
        [
            [Paragraph(f"Period {first_date} – {last_date}", styles["GrandTitle"]),
             Paragraph(f"Totalt {total_km} km", styles["GrandVal"])]
        ],
        colWidths=[sum(col_widths[:-1]), col_widths[-1]]
    )
    grand.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 1.0, colors.HexColor("#777777")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#EDEDED")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(grand)

    doc.build(story, onFirstPage=_page_fn, onLaterPages=_page_fn)
    pdf = buf.getvalue()
    buf.close()
    return pdf
