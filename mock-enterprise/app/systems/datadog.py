"""Mock Datadog API.

Real API shape: GET /api/v1/slo
Response: {"data": [...]}
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import DDService, DDSLO, DDMonitorStatus, DDIncident

router = APIRouter(prefix="/api/datadog", tags=["Datadog"])


def _serialize(obj):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _dd_response(data: list) -> dict:
    """Mimic Datadog API response shape."""
    return {"data": data}


# --- Services ---

@router.get("/services")
def list_services(
    environment: str = "production",
    db: Session = Depends(get_db),
):
    services = db.query(DDService).filter(DDService.environment == environment).all()
    return _dd_response([_serialize(s) for s in services])


@router.get("/services/{service_id}")
def get_service(service_id: str, db: Session = Depends(get_db)):
    svc = db.query(DDService).filter(DDService.id == service_id).first()
    if not svc:
        return {"errors": ["Service not found"]}
    result = _serialize(svc)
    result["slos"] = [_serialize(s) for s in db.query(DDSLO).filter(DDSLO.service_id == service_id).all()]
    result["monitors"] = [_serialize(m) for m in db.query(DDMonitorStatus).filter(DDMonitorStatus.service_id == service_id).all()]
    return {"data": result}


# --- SLOs ---

@router.get("/slo")
def list_slos(
    service_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DDSLO)
    if service_id:
        query = query.filter(DDSLO.service_id == service_id)
    if status:
        query = query.filter(DDSLO.status == status)
    return _dd_response([_serialize(s) for s in query.all()])


@router.get("/slo/summary")
def slo_summary(db: Session = Depends(get_db)):
    """Overall SLO health summary."""
    total = db.query(DDSLO).count()
    ok = db.query(DDSLO).filter(DDSLO.status == "OK").count()
    warning = db.query(DDSLO).filter(DDSLO.status == "Warning").count()
    breached = db.query(DDSLO).filter(DDSLO.status == "Breached").count()
    avg_budget = db.query(func.avg(DDSLO.error_budget_remaining)).scalar()
    return {
        "data": {
            "total": total,
            "ok": ok,
            "warning": warning,
            "breached": breached,
            "avg_error_budget_remaining": round(avg_budget or 0, 2),
        }
    }


@router.get("/slo/{slo_id}")
def get_slo(slo_id: str, db: Session = Depends(get_db)):
    slo = db.query(DDSLO).filter(DDSLO.id == slo_id).first()
    if not slo:
        return {"errors": ["SLO not found"]}
    return {"data": _serialize(slo)}


# --- Monitors ---

@router.get("/monitors")
def list_monitors(
    service_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DDMonitorStatus)
    if service_id:
        query = query.filter(DDMonitorStatus.service_id == service_id)
    if status:
        query = query.filter(DDMonitorStatus.status == status)
    return _dd_response([_serialize(m) for m in query.all()])


# --- Incidents ---

@router.get("/incidents")
def list_incidents(
    severity: str | None = None,
    status: str | None = None,
    service_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(DDIncident)
    if severity:
        query = query.filter(DDIncident.severity == severity)
    if status:
        query = query.filter(DDIncident.status == status)
    if service_id:
        query = query.filter(DDIncident.service_id == service_id)
    return _dd_response([_serialize(i) for i in query.order_by(DDIncident.created_at.desc()).all()])


@router.get("/incidents/stats")
def incident_stats(db: Session = Depends(get_db)):
    total = db.query(DDIncident).count()
    active = db.query(DDIncident).filter(DDIncident.status == "Active").count()
    avg_duration = db.query(func.avg(DDIncident.duration_minutes)).filter(
        DDIncident.duration_minutes.isnot(None)
    ).scalar()
    customer_impacting = db.query(DDIncident).filter(DDIncident.customer_impact.is_(True)).count()
    by_severity = {}
    for sev in ["SEV-1", "SEV-2", "SEV-3", "SEV-4"]:
        by_severity[sev] = db.query(DDIncident).filter(DDIncident.severity == sev).count()
    return {
        "data": {
            "total": total,
            "active": active,
            "avg_duration_minutes": round(avg_duration or 0, 1),
            "customer_impacting": customer_impacting,
            "by_severity": by_severity,
        }
    }


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(DDIncident).filter(DDIncident.id == incident_id).first()
    if not inc:
        return {"errors": ["Incident not found"]}
    return {"data": _serialize(inc)}
