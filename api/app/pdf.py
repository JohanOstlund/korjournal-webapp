from io import BytesIO
from typing import List, Dict, Any, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

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

def _to_float_or_none(v: Any):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return None

def _month_key(yyyy_mm_dd: str) -> Tuple[int, int]:
    # yyyy-mm-dd -> (yyyy, mm)
    try:
        y = int(yyyy_mm_dd[0:4])
        m = int(yyyy_mm_dd[5:7])
        return (y, m)
    except Exception:
        return (0, 0)

def render_journal_pdf(rows: List[Dict[str, Any]]) -> bytes:
    """
    rows: lista av dicts (från API) med nycklar:
      - datum (str 'YYYY-MM-DD')
      - regnr (str)         [NY]
      - driver (str)        [NY]
      - start_odo (float|str|None)
      - end_odo   (float|str|None)
      - km        (float|str|None)
      - syfte     (str|None)
      - tjanst    (bool)
      - start_adress (str|None)
      - slut_adress  (str|None)

    PDF: kolumner = Datum | Regnr | Förare | Mätarställning start | Mätarställning slut | Antal km | Syfte | Typ
    Efter varje månads sista rad skrivs en summeringsrad: "Summa YYYY-MM"
    Och sist: "Totalt" för hela perioden.
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
    styles.add(ParagraphStyle(name="CellBold", fontName="Helvetica-Bold", fontSize=9, leading=12))

    story = []

    # Titel + period
    story.append(Paragraph("Körjournal", styles["TitleSE"]))
    if rows:
        first = rows[0].get("datum", "")
        last = rows[-1].get("datum", "")
        story.append(Paragraph(f"Period: {first} – {last}", styles["SubtitleSE"]))
    story.append(Spacer(1, 4*mm))

    # Kolumnhuvud
    headers = [
        "Datum",
        "Regnr",
        "Förare",
        "Mätarställning start",
        "Mätarställning slut",
        "Antal km",
        "Syfte",
        "Typ",
    ]
    data = [headers]

    # För summerings-styling spårar vi index för månadsrader och totalsrad
    summary_row_indexes = []  # list[(row_index, is_total: bool)]

    # Summeringar
    total_km = 0.0
    month_km = 0.0
    cur_month = None

    # Vi förutsätter att rows är sorterad stigande (API gör asc)
    # Gå igenom rader och mata tabellen, samt detektera månadsskifte
    def append_month_summary(month_key_tuple: Tuple[int, int]):
        nonlocal data, month_km, summary_row_indexes
        y, m = month_key_tuple
        # Skriv en rad med månads-summa precis här
        label = f"Summa {y:04d}-{m:02d}"
        # tomma i de flesta kolumner, visa label i "Syfte"-kolumnen och summa i "Antal km"
        row = [
            Paragraph("", styles["CellBold"]),   # Datum
            Paragraph("", styles["CellBold"]),   # Regnr
            Paragraph("", styles["CellBold"]),   # Förare
            Paragraph("", styles["CellBold"]),   # Start odo
            Paragraph("", styles["CellBold"]),   # End odo
            Paragraph(f"{round(month_km, 1)}", styles["CellBold"]),  # Km
            Paragraph(label, styles["CellBold"]),                    # Syfte (label)
            Paragraph("", styles["CellBold"]),                       # Typ
        ]
        data.append(row)
        summary_row_indexes.append((len(data)-1, False))  # False = månads-summa
        month_km = 0.0  # reset

    for idx, r in enumerate(rows):
        datum = r.get("datum", "")
        regnr = r.get("regnr", "") or r.get("vehicle_reg", "") or ""
        driver = r.get("driver", "") or r.get("driver_name", "") or ""
        start_odo = r.get("start_odo", "")
        end_odo = r.get("end_odo", "")
        km_val = _to_float_or_none(r.get("km"))
        syfte = r.get("syfte", "") or ""
        typ = _format_bool_tjanst(r.get("tjanst"))

        # Månadsskifte?
        this_month = _month_key(datum) if datum else None
        if cur_month is None and this_month is not None:
            cur_month = this_month
        elif this_month is not None and cur_month != this_month:
            # skriv ut summering för föregående månad innan vi byter
            append_month_summary(cur_month)
            cur_month = this_month

        # Lägg till rad
        row = [
            Paragraph(str(datum), styles["Cell"]),
            Paragraph(str(regnr), styles["Cell"]),
            Paragraph(str(driver), styles["Cell"]),
            Paragraph("" if start_odo is None else str(start_odo), styles["Cell"]),
            Paragraph("" if end_odo is None else str(end_odo), styles["Cell"]),
            Paragraph("" if km_val is None else str(round(km_val, 1)), styles["Cell"]),
            Paragraph(str(syfte), styles["Cell"]),
            Paragraph(typ, styles["Cell"]),
        ]
        data.append(row)

        # Adresser i en extra "grå" rad
        sa = r.get("start_adress") or ""
        ea = r.get("slut_adress") or ""
        if sa or ea:
            addr_txt = []
            if sa: addr_txt.append(f"Start: {sa}")
            if ea: addr_txt.append(f"Slut: {ea}")
            data.append([
                Paragraph("", styles["CellSmall"]),   # Datum
                Paragraph("", styles["CellSmall"]),   # Regnr
                Paragraph("", styles["CellSmall"]),   # Förare
                Paragraph("", styles["CellSmall"]),   # Start odo
                Paragraph("", styles["CellSmall"]),   # End odo
                Paragraph("", styles["CellSmall"]),   # Km
                Paragraph("<br/>".join(addr_txt), styles["CellSmall"]),  # Syfte (addr)
                Paragraph("", styles["CellSmall"]),   # Typ
            ])

        # Summeringar
        if km_val is not None:
            total_km += km_val
            month_km += km_val

    # Sista månadens summering, om någon rad fanns
    if rows and cur_month is not None:
        append_month_summary(cur_month)

    # Totalsumma
    total_row = [
        Paragraph("", styles["CellBold"]),  # Datum
        Paragraph("", styles["CellBold"]),  # Regnr
        Paragraph("", styles["CellBold"]),  # Förare
        Paragraph("", styles["CellBold"]),  # Start odo
        Paragraph("", styles["CellBold"]),  # End odo
        Paragraph(f"{round(total_km, 1)}", styles["CellBold"]),  # Km
        Paragraph("Totalt", styles["CellBold"]),                 # Syfte (label)
        Paragraph("", styles["CellBold"]),                       # Typ
    ]
    data.append(total_row)
    summary_row_indexes.append((len(data)-1, True))  # True = totalsumma

    # Kolumnbredder: A4 (210mm) - marginaler (30mm) ≈ 180mm
    # Datum 18, Regnr 18, Förare 22, Start 24, Slut 24, Km 14, Syfte 48, Typ 12  => sum 180
    col_widths_mm = [18, 18, 22, 24, 24, 14, 48, 12]
    col_widths = [w * mm for w in col_widths_mm]

    tbl = Table(data, colWidths=col_widths, repeatRows=1)

    # Bas-stilar
    base_style = [
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

    # Summeraders styling (månads & total)
    for idx, is_total in summary_row_indexes:
        base_style += [
            ("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#F2F2F2")),
            ("FONT", (0, idx), (-1, idx), "Helvetica-Bold", 9),
        ]
        # Högerjustera km-kolumnen för summeringen
        base_style += [("ALIGN", (5, idx), (5, idx), "RIGHT")]

    tbl.setStyle(TableStyle(base_style))

    story.append(tbl)

    doc.build(story, onFirstPage=_page_fn, onLaterPages=_page_fn)
    pdf = buf.getvalue()
    buf.close()
    return pdf
