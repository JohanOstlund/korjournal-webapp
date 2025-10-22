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

def _ym(datum: str) -> str:
    return (datum or "")[:7]  # 'YYYY-MM-DD' -> 'YYYY-MM'

def _collect_month_totals(rows: List[Dict[str, Any]]) -> Tuple[Dict[str, float], float]:
    per_month = {}
    total = 0.0
    for r in rows:
        km = r.get("km")
        try:
            v = float(km) if km not in (None, "") else 0.0
        except Exception:
            v = 0.0
        m = _ym(r.get("datum", ""))
        if m:
            per_month[m] = per_month.get(m, 0.0) + v
        total += v
    return per_month, total

def render_journal_pdf(rows: List[Dict[str, Any]]) -> bytes:
    """
    rows: list av dicts:
      - datum (YYYY-MM-DD)
      - regnr/vehicle_reg (valfritt)
      - driver/driver_name (valfritt)
      - start_odo, end_odo, km
      - syfte, tjanst (bool)
      - start_adress, slut_adress (valfritt)
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
    styles.add(ParagraphStyle(name="CellSmallGrey", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey))
    styles.add(ParagraphStyle(name="Head", fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=1))   # center
    styles.add(ParagraphStyle(name="SumRow", fontName="Helvetica-Bold", fontSize=10, leading=13, alignment=1)) # center

    story = []

    # Titel + period
    story.append(Paragraph("Körjournal", styles["TitleSE"]))
    if rows:
        first = rows[0].get("datum", "")
        last = rows[-1].get("datum", "")
        story.append(Paragraph(f"Period: {first} – {last}", styles["SubtitleSE"]))
    story.append(Spacer(1, 4*mm))

    # Header (två rader via \n)
    headers = [
        "Datum",
        "Regnr",
        "Förare",
        "Mätarställning\nstart",
        "Mätarställning\nslut",
        "Antal\nkm",
        "Syfte",
        "Typ",
    ]
    data: List[List[Any]] = [[Paragraph(h, styles["Head"]) for h in headers]]

    # Kolumnbredder (≈180 mm). Syfte ~1/3 smalare.
    col_widths_mm = [18, 18, 24, 24, 24, 16, 36, 12]
    col_widths = [w * mm for w in col_widths_mm]

    per_month, total_sum = _collect_month_totals(rows)

    # Hjälpare för helbredds-summeringsrader (en cell som spänner hela tabellen)
    def _append_sum_row(text: str):
        # skapa rad med första cellen = text, resten placeholders
        row = [Paragraph(text, styles["SumRow"])] + [""] * (len(headers) - 1)
        data.append(row)
        r_idx = len(data) - 1
        sum_rows.append(r_idx)

    sum_rows: List[int] = []

    # Resrader – adresser bäddas in i syfte-cellen så hela resan håller ihop på en sida
    for i, r in enumerate(rows):
        datum = r.get("datum", "")
        regnr = r.get("regnr") or r.get("vehicle_reg") or ""
        driver = r.get("driver") or r.get("driver_name") or ""
        start_odo = "" if r.get("start_odo") is None else str(r.get("start_odo"))
        end_odo   = "" if r.get("end_odo") is None else str(r.get("end_odo"))
        km        = "" if r.get("km") is None else str(r.get("km"))
        syfte     = r.get("syfte", "") or ""
        typ       = _format_bool_tjanst(r.get("tjanst"))

        sa = (r.get("start_adress") or "").strip()
        ea = (r.get("slut_adress") or "").strip()
        addr_html = ""
        if sa or ea:
            parts = []
            if sa: parts.append(f"<font color='#666666' size='8'>Start: {sa}</font>")
            if ea: parts.append(f"<font color='#666666' size='8'>Slut: {ea}</font>")
            addr_html = "<br/>" + "<br/>".join(parts)

        syfte_html = f"{syfte}{addr_html}"

        data.append([
            Paragraph(str(datum), styles["Cell"]),
            Paragraph(str(regnr), styles["Cell"]),
            Paragraph(str(driver), styles["Cell"]),
            Paragraph(start_odo, styles["Cell"]),
            Paragraph(end_odo, styles["Cell"]),
            Paragraph(km, styles["Cell"]),
            Paragraph(syfte_html, styles["Cell"]),
            Paragraph(typ, styles["Cell"]),
        ])

        # Månadsgräns? Lägg helbredds-summarad
        cur_m = _ym(datum)
        next_m = _ym(rows[i+1].get("datum","")) if i+1 < len(rows) else None
        if next_m != cur_m:
            _append_sum_row(f"Summa {cur_m}  <b>{round(per_month.get(cur_m, 0.0), 1)}</b> km")

    # Totalsumma (helbredds-rad)
    if rows:
        _append_sum_row(f"Totalt  <b>{round(total_sum, 1)}</b> km")

    # Bygg tabell
    tbl = Table(data, colWidths=col_widths, repeatRows=1)

    # Basstil
    ts = [
        ("FONT", (0,0), (-1,0), "Helvetica-Bold", 9),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
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

    # Styla helbredds-summor: SPAN över hela bredden, centrerad, grå bakgrund, ram och extra padding
    for r in sum_rows:
        ts += [
            ("SPAN", (0, r), (-1, r)),
            ("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F5F5F5")),
            ("BOX", (0, r), (-1, r), 0.75, colors.HexColor("#BDBDBD")),
            ("ALIGN", (0, r), (-1, r), "CENTER"),
            ("TOPPADDING", (0, r), (-1, r), 6),
            ("BOTTOMPADDING", (0, r), (-1, r), 6),
        ]

    tbl.setStyle(TableStyle(ts))
    story.append(tbl)

    doc.build(story, onFirstPage=_page_fn, onLaterPages=_page_fn)
    pdf = buf.getvalue()
    buf.close()
    return pdf
