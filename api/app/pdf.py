from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from typing import List, Dict

def render_journal_pdf(rows: List[Dict]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    def header(page):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20*mm, height-20*mm, "Körjournal – Sammanställning")
        c.setFont("Helvetica", 9)
        c.drawString(20*mm, height-26*mm, "År/Regnr/Period enligt rapportinställning")

    y = height - 35*mm
    header(1)

    cols = [
        ("Datum", 25), ("Start", 18), ("Slut", 18), ("Km", 12),
        ("Startadress", 45), ("Slutadress", 45), ("Syfte", 45), ("Tjänst", 12)
    ]

    c.setFont("Helvetica-Bold", 8)
    x = 15*mm
    for title, w in cols:
        c.drawString(x, y, title)
        x += w*mm
    y -= 6*mm
    c.setFont("Helvetica", 8)

    for r in rows:
        if y < 25*mm:
            c.showPage(); y = height - 20*mm; header(1)
            y -= 15*mm
            c.setFont("Helvetica-Bold", 8)
            x = 15*mm
            for title, w in cols:
                c.drawString(x, y, title)
                x += w*mm
            y -= 6*mm
            c.setFont("Helvetica", 8)

        x = 15*mm
        vals = [
            r.get("datum",""),
            str(r.get("start_odo","")),
            str(r.get("end_odo","")),
            str(r.get("km","")),
            r.get("start_adress",""),
            r.get("slut_adress",""),
            r.get("syfte",""),
            "Ja" if r.get("tjanst", True) else "Nej",
        ]
        for v, (_, w) in zip(vals, cols):
            c.drawString(x, y, v[:40])
            x += w*mm
        y -= 5.5*mm

    c.setFont("Helvetica", 9)
    c.rect(15*mm, 10*mm, 180*mm, 10*mm)
    c.drawString(17*mm, 13*mm, "Jag intygar att uppgifterna ovan är korrekta:  Ort/Datum: __________  Namn: __________  Namnteckning: __________")

    c.save()
    return buf.getvalue()
