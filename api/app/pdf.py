from io import BytesIO
from typing import List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

def _format_bool_tjanst(val: Any) -> str:
    # True => Tjänst, False => Privat, annars tomt
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

def render_journal_pdf(rows: List[Dict[str, Any]]) -> bytes:
    """
    rows: lista av dicts med nycklar (som API:t redan skickar):
      - datum (str 'YYYY-MM-DD')
      - start_odo (float|str|None)
      - end_odo   (float|str|None)
      - km        (float|str|None)
      - syfte     (str|None)
      - tjanst    (bool)
      - start_adress (str|None)  [kan finnas]
      - slut_adress  (str|None)  [kan finnas]
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

    story = []

    # Titel + liten sammanfattning av datumintervall
    story.append(Paragraph("Körjournal", styles["TitleSE"]))
    if rows:
        first = rows[0]["datum"]
        last = rows[-1]["datum"]
        # Om listan redan är sorterad kronologiskt stigande i exporten
        # (export_pdf gör asc) – säkerställ rätt ordning:
        try:
            first, last = (rows[0]["datum"], rows[-1]["datum"])
        except Exception:
            pass
        story.append(Paragraph(f"Period: {first} – {last}", styles["SubtitleSE"]))
    story.append(Spacer(1, 4*mm))

    # Tabellhuvud – MED mätarställning start/slut
    headers = [
        "Datum",
        "Mätarställning start",
        "Mätarställning slut",
        "Antal km",
        "Syfte",
        "Typ",
    ]

    data = [headers]

    # Rader
    for r in rows:
        datum = r.get("datum", "")
        start_odo = r.get("start_odo", "")
        end_odo = r.get("end_odo", "")
        km = r.get("km", "")
        syfte = r.get("syfte", "") or ""
        typ = _format_bool_tjanst(r.get("tjanst"))

        # Gör textceller som Paragraphs för snygg radbrytning
        syfte_p = Paragraph(str(syfte), styles["Cell"])
        row = [
            Paragraph(str(datum), styles["Cell"]),
            Paragraph("" if start_odo is None else str(start_odo), styles["Cell"]),
            Paragraph("" if end_odo is None else str(end_odo), styles["Cell"]),
            Paragraph("" if km is None else str(km), styles["Cell"]),
            syfte_p,
            Paragraph(typ, styles["Cell"]),
        ]
        data.append(row)

        # (Valfritt) visa adresser i liten grå text under raden
        sa = r.get("start_adress") or ""
        ea = r.get("slut_adress") or ""
        if sa or ea:
            addr_txt = []
            if sa: addr_txt.append(f"Start: {sa}")
            if ea: addr_txt.append(f"Slut: {ea}")
            data.append([
                Paragraph("", styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
                Paragraph("<br/>".join(addr_txt), styles["CellSmall"]),
                Paragraph("", styles["CellSmall"]),
            ])

    # Kolumnbredder (mm → pt)
    # A4 bredd (210mm) - marginaler (30mm) ≈ 180mm till tabellen
    # Fördela: Datum 20mm, Start 32mm, Slut 32mm, Km 18mm, Syfte 60mm, Typ 18mm
    col_widths_mm = [20, 32, 32, 18, 60, 18]
    col_widths = [w * mm for w in col_widths_mm]

    tbl = Table(data, colWidths=col_widths, repeatRows=1)

    tbl.setStyle(TableStyle([
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
    ]))

    story.append(tbl)

    doc.build(story, onFirstPage=_page_fn, onLaterPages=_page_fn)
    pdf = buf.getvalue()
    buf.close()
    return pdf