from io import BytesIO
from typing import List, Dict, Any, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

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

def _month_key(iso_date: str) -> str:
    # iso_date: 'YYYY-MM-DD' -> 'YYYY-MM'
    return (iso_date or "")[:7]

def _to_par(text: Any, style) -> Paragraph:
    return Paragraph("" if text is None else str(text), style)

def render_journal_pdf(rows: List[Dict[str, Any]]) -> bytes:
    """
    Förväntade nycklar per rad:
      - datum (YYYY-MM-DD)
      - regnr (valfritt)            <-- visas i kolumn
      - driver / driver_name (valfritt)  <-- visas i kolumn "Förare"
      - start_odo, end_odo, km
      - syfte, tjanst (bool)
      - start_adress, slut_adress (valfria)
    Vi grupperar månadsvis (YYYY-MM) och lägger in en summeringsrad efter varje månad,
    samt en totalsumma i slutet. Summeringsraderna ramas in och visar "km".
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
    styles.add(ParagraphStyle(name="Head", fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=1))  # centered header
    styles.add(ParagraphStyle(name="SumText", fontName="Helvetica-Bold", fontSize=9, leading=12, alignment=2)) # right
    styles.add(ParagraphStyle(name="SumKm", fontName="Helvetica-Bold", fontSize=9, leading=12, alignment=1))   # center

    story = []

    # Titel + period
    story.append(Paragraph("Körjournal", styles["TitleSE"]))
    if rows:
        first = rows[0].get("datum", "")
        last = rows[-1].get("datum", "")
        story.append(Paragraph(f"Period: {first} – {last}", styles["SubtitleSE"]))
    story.append(Spacer(1, 4*mm))

    # ---- Tabellhuvud: två-radiga rubriker för mätarställning ----
    headers = [
        _to_par("Datum", styles["Head"]),
        _to_par("Regnr", styles["Head"]),
        _to_par("Förare", styles["Head"]),
        Paragraph("Mätarställning<br/>start", styles["Head"]),
        Paragraph("Mätarställning<br/>slut", styles["Head"]),
        _to_par("Antal km", styles["Head"]),
        _to_par("Syfte", styles["Head"]),
        _to_par("Typ", styles["Head"]),
    ]

    data: List[List[Any]] = [headers]

    # Kolumnbredder: total ~ 180mm (A4 210 - 2*15)
    # Datum 18, Regnr 18, Förare 22, Start 26, Slut 26, Km 16, Syfte 40 (≈ -1/3), Typ 14  => 180
    col_widths_mm = [18, 18, 22, 26, 26, 16, 40, 14]
    col_widths = [w * mm for w in col_widths_mm]

    # För summeringsrad-styling behöver vi hålla koll på vilka rader som är summeringsrader
    sum_row_ranges: List[Tuple[int, int]] = []  # (start_col, end_col) används för BOX
    sum_row_indices: List[int] = []             # vilka radindex i data som är summeringar
    total_km = 0.0

    # För månadsvis summering
    current_month = None
    month_km_acc = 0.0

    def flush_month_sum(month_key: str):
        nonlocal data, sum_row_ranges, sum_row_indices, month_km_acc
        if month_key is None:
            return
        # Rad med en label som spänner flera kolumner + km i km-kolumnen
        # Vi lägger label i kol 0..4 (datum..slut), km i kol 5, tomt i kol 6..7
        label = _to_par(f"Summa {month_key}", styles["SumText"])
        km_txt = _to_par(f"{round(month_km_acc, 1)} km", styles["SumKm"])
        row = ["", "", "", "", "", "", "", ""]  # 8 kolumner
        row[0] = label
        row[5] = km_txt
        data.append(row)
        r_idx = len(data) - 1

        # Span label över kol 0..4, lämna km i 5, vi bokar en BOX över hela raden 0..7
        ts_cmds.extend([
            ("SPAN", (0, r_idx), (4, r_idx)),
        ])
        sum_row_ranges.append((0, 7))
        sum_row_indices.append(r_idx)

        # nollställ ackumulatorn
        month_km_acc = 0.0

    # Tabellstil – sätts upp, och fylls på efter att data byggts
    ts_cmds = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
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
    ]

    # ---- Rader ----
    for r in rows:
        datum = r.get("datum", "")
        month = _month_key(datum)

        # vid månadsskifte -> skriv månadssumma-rad för föregående
        if current_month is None:
            current_month = month
        elif month != current_month:
            flush_month_sum(current_month)
            current_month = month

        regnr = r.get("regnr") or r.get("vehicle_reg") or ""
        driver = r.get("driver") or r.get("driver_name") or ""
        start_odo = r.get("start_odo", "")
        end_odo = r.get("end_odo", "")
        km = r.get("km", "")
        syfte = r.get("syfte", "") or ""
        typ = _format_bool_tjanst(r.get("tjanst"))

        # summera km (om numeriskt)
        try:
            km_val = float(km)
            month_km_acc += km_val
            total_km += km_val
        except Exception:
            pass

        # huvudrad
        row = [
            _to_par(datum, styles["Cell"]),
            _to_par(regnr, styles["Cell"]),
            _to_par(driver, styles["Cell"]),
            _to_par("" if start_odo is None else start_odo, styles["Cell"]),
            _to_par("" if end_odo is None else end_odo, styles["Cell"]),
            _to_par("" if km is None else km, styles["Cell"]),
            _to_par(syfte, styles["Cell"]),
            _to_par(typ, styles["Cell"]),
        ]
        data.append(row)

        # adressrad i liten grå text
        sa = r.get("start_adress") or ""
        ea = r.get("slut_adress") or ""
        if sa or ea:
            addr_txt = []
            if sa: addr_txt.append(f"Start: {sa}")
            if ea: addr_txt.append(f"Slut: {ea}")
            data.append([
                _to_par("", styles["CellSmall"]),
                _to_par("", styles["CellSmall"]),
                _to_par("", styles["CellSmall"]),
                _to_par("", styles["CellSmall"]),
                _to_par("", styles["CellSmall"]),
                _to_par("", styles["CellSmall"]),
                Paragraph("<br/>".join(addr_txt), styles["CellSmall"]),
                _to_par("", styles["CellSmall"]),
            ])

    # sista månadssumman
    if current_month is not None:
        flush_month_sum(current_month)

    # totalsumma längst ned
    if rows:
        total_row = ["", "", "", "", "", "", "", ""]
        total_row[0] = _to_par("Totalt", styles["SumText"])
        total_row[5] = _to_par(f"{round(total_km, 1)} km", styles["SumKm"])
        data.append(total_row)
        r_idx = len(data) - 1
        ts_cmds.extend([
            ("SPAN", (0, r_idx), (4, r_idx)),
        ])
        sum_row_ranges.append((0, 7))
        sum_row_indices.append(r_idx)

    # Bygg tabellen
    tbl = Table(data, colWidths=col_widths, repeatRows=1)

    # Lägg till BOX + bakgrund för varje summeringsrad
    for r_idx in sum_row_indices:
        ts_cmds.extend([
            ("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F5F5F5")),
            ("BOX", (0, r_idx), (-1, r_idx), 1.0, colors.HexColor("#999999")),
        ])

    tbl.setStyle(TableStyle(ts_cmds))

    story.append(tbl)

    doc.build(story, onFirstPage=_page_fn, onLaterPages=_page_fn)
    pdf = buf.getvalue()
    buf.close()
    return pdf
