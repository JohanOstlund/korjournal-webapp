"""
Export routes for CSV and PDF journal generation.
"""
import csv
import logging
from datetime import datetime
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Trip, Vehicle, User
from ..dependencies import get_current_user
from ..pdf import render_journal_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exports", tags=["exports"])

@router.get("/journal.csv")
def export_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    """Export trips as CSV."""
    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.user_id == user.id)
    if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
    if year:
        q = q.filter(Trip.started_at >= datetime(year, 1, 1), Trip.started_at < datetime(year + 1, 1, 1))
    q = q.filter(Trip.ended_at.isnot(None))

    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "År", "Regnr", "Datum", "Startadress", "Slutadress",
        "Start mätarställning", "Slut mätarställning", "Antal km", "Ärende/Syfte", "Förare", "Tjänst/Privat"
    ])

    for t, v in q.order_by(Trip.started_at.asc()).all():
        datum = t.started_at.strftime('%Y-%m-%d') if t.started_at else ""
        writer.writerow([
            t.started_at.year if t.started_at else "",
            v.reg_no, datum,
            t.start_address or "",
            t.end_address or "",
            t.start_odometer_km or "", t.end_odometer_km or "",
            t.distance_km or "",
            t.purpose or "",
            t.driver_name or "",
            "Tjänst" if t.business else "Privat",
        ])

    csv_bytes = output.getvalue().encode('utf-8-sig')
    logger.info(f"CSV export for user: {user.username}")
    return Response(content=csv_bytes, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=korjournal.csv"})

@router.get("/journal.pdf")
def export_pdf_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    vehicle: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    """Export trips as PDF."""
    q = db.query(Trip, Vehicle).join(Vehicle, Trip.vehicle_id == Vehicle.id).filter(Trip.user_id == user.id)
    if vehicle: q = q.filter(Vehicle.reg_no == vehicle)
    if year:
        q = q.filter(Trip.started_at >= datetime(year, 1, 1), Trip.started_at < datetime(year + 1, 1, 1))
    q = q.filter(Trip.ended_at.isnot(None))

    rows = []
    for t, v in q.order_by(Trip.started_at.asc()).all():
        rows.append({
            "datum": t.started_at.strftime('%Y-%m-%d') if t.started_at else "",
            "start_odo": t.start_odometer_km or "",
            "end_odo": t.end_odometer_km or "",
            "km": t.distance_km or "",
            "start_adress": t.start_address or "",
            "slut_adress": t.end_address or "",
            "syfte": t.purpose or "",
            "tjanst": t.business,
        })

    pdf_bytes = render_journal_pdf(rows)
    logger.info(f"PDF export for user: {user.username}")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=korjournal.pdf"})
