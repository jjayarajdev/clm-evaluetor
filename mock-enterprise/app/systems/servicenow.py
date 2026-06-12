"""Mock ServiceNow Table API.

Real API shape: GET /api/now/table/incident
Response: {"result": [...]}
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import SNOWSLAResult, SNOWIncident, SNOWChangeRequest

router = APIRouter(prefix="/api/snow", tags=["ServiceNow"])


def _serialize(obj):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _table_response(result: list) -> dict:
    """Mimic ServiceNow Table API response."""
    return {"result": result}


# --- SLA Results ---

@router.get("/sla-results")
def list_sla_results(
    service_name: str | None = None,
    metric_type: str | None = None,
    period: str | None = None,
    is_met: bool | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SNOWSLAResult)
    if service_name:
        query = query.filter(SNOWSLAResult.service_name == service_name)
    if metric_type:
        query = query.filter(SNOWSLAResult.metric_type == metric_type)
    if period:
        query = query.filter(SNOWSLAResult.measurement_period == period)
    if is_met is not None:
        query = query.filter(SNOWSLAResult.is_met == is_met)
    return _table_response([_serialize(s) for s in query.order_by(SNOWSLAResult.measurement_date.desc()).all()])


@router.get("/sla-results/summary")
def sla_summary(
    service_name: str | None = None,
    db: Session = Depends(get_db),
):
    """Aggregate SLA compliance summary."""
    query = db.query(SNOWSLAResult)
    if service_name:
        query = query.filter(SNOWSLAResult.service_name == service_name)
    total = query.count()
    met = query.filter(SNOWSLAResult.is_met.is_(True)).count()
    breaches = db.query(func.sum(SNOWSLAResult.breach_count)).scalar() or 0
    credits = db.query(func.sum(SNOWSLAResult.credit_amount)).scalar() or 0
    return {
        "total_measurements": total,
        "met": met,
        "missed": total - met,
        "compliance_rate": round((met / total * 100), 2) if total > 0 else 0,
        "total_breaches": breaches,
        "total_credits": round(credits, 2),
    }


# --- Incidents ---

@router.get("/incidents")
def list_incidents(
    priority: str | None = None,
    state: str | None = None,
    service_name: str | None = None,
    sla_breached: bool | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SNOWIncident)
    if priority:
        query = query.filter(SNOWIncident.priority == priority)
    if state:
        query = query.filter(SNOWIncident.state == state)
    if service_name:
        query = query.filter(SNOWIncident.service_name == service_name)
    if sla_breached is not None:
        query = query.filter(SNOWIncident.sla_breached == sla_breached)
    return _table_response([_serialize(i) for i in query.order_by(SNOWIncident.opened_at.desc()).all()])


@router.get("/incidents/stats")
def incident_stats(
    service_name: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SNOWIncident)
    if service_name:
        query = query.filter(SNOWIncident.service_name == service_name)
    total = query.count()
    by_priority = {}
    for p in ["P1", "P2", "P3", "P4"]:
        by_priority[p] = query.filter(SNOWIncident.priority == p).count()
    breached = query.filter(SNOWIncident.sla_breached.is_(True)).count()
    avg_resolution = db.query(func.avg(SNOWIncident.resolution_time_minutes)).filter(
        SNOWIncident.resolution_time_minutes.isnot(None)
    ).scalar()
    return {
        "total_incidents": total,
        "by_priority": by_priority,
        "sla_breached": breached,
        "avg_resolution_minutes": round(avg_resolution or 0, 1),
    }


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(SNOWIncident).filter(SNOWIncident.id == incident_id).first()
    if not inc:
        return {"error": {"message": "Record not found"}}
    return {"result": _serialize(inc)}


# --- Change Requests ---

@router.get("/changes")
def list_changes(
    change_type: str | None = None,
    state: str | None = None,
    service_name: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SNOWChangeRequest)
    if change_type:
        query = query.filter(SNOWChangeRequest.change_type == change_type)
    if state:
        query = query.filter(SNOWChangeRequest.state == state)
    if service_name:
        query = query.filter(SNOWChangeRequest.service_name == service_name)
    return _table_response([_serialize(c) for c in query.order_by(SNOWChangeRequest.planned_start.desc()).all()])


@router.get("/changes/{change_id}")
def get_change(change_id: str, db: Session = Depends(get_db)):
    chg = db.query(SNOWChangeRequest).filter(SNOWChangeRequest.id == change_id).first()
    if not chg:
        return {"error": {"message": "Record not found"}}
    return {"result": _serialize(chg)}
