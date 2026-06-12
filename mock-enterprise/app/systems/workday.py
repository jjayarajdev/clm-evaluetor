"""Mock Workday RaaS (Reporting as a Service) API.

Real API shape: GET /ccx/service/{tenant}/workers
Response: {"Report_Entry": [...], "total": N}
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import WDWorker, WDOrganization, WDPosition


router = APIRouter(prefix="/api/workday", tags=["Workday"])


def _serialize(obj):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _raas_response(entries: list) -> dict:
    """Mimic Workday RaaS response shape."""
    return {"Report_Entry": entries, "total": len(entries)}


# --- Workers ---

@router.get("/workers")
def list_workers(
    department: str | None = None,
    status: str = "Active",
    manager_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(WDWorker).filter(WDWorker.status == status)
    if department:
        query = query.filter(WDWorker.department == department)
    if manager_id:
        query = query.filter(WDWorker.manager_id == manager_id)
    workers = query.all()
    return _raas_response([_serialize(w) for w in workers])


@router.get("/workers/{worker_id}")
def get_worker(worker_id: str, db: Session = Depends(get_db)):
    worker = db.query(WDWorker).filter(WDWorker.id == worker_id).first()
    if not worker:
        return {"error": "Worker not found"}
    result = _serialize(worker)
    # Include direct reports
    reports = db.query(WDWorker).filter(WDWorker.manager_id == worker_id).all()
    result["direct_reports"] = [_serialize(r) for r in reports]
    return result


@router.get("/workers/{worker_id}/org-chart")
def get_org_chart(worker_id: str, db: Session = Depends(get_db)):
    """Get org chart from a worker upward."""
    chain = []
    current = db.query(WDWorker).filter(WDWorker.id == worker_id).first()
    while current:
        chain.append(_serialize(current))
        if current.manager_id:
            current = db.query(WDWorker).filter(WDWorker.id == current.manager_id).first()
        else:
            current = None
    return {"worker_id": worker_id, "reporting_chain": chain}


# --- Organizations ---

@router.get("/organizations")
def list_organizations(
    org_type: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(WDOrganization).filter(WDOrganization.is_active.is_(True))
    if org_type:
        query = query.filter(WDOrganization.org_type == org_type)
    return _raas_response([_serialize(o) for o in query.all()])


@router.get("/organizations/{org_id}")
def get_organization(org_id: str, db: Session = Depends(get_db)):
    org = db.query(WDOrganization).filter(WDOrganization.id == org_id).first()
    if not org:
        return {"error": "Organization not found"}
    result = _serialize(org)
    children = db.query(WDOrganization).filter(WDOrganization.parent_id == org_id).all()
    result["sub_organizations"] = [_serialize(c) for c in children]
    return result


@router.get("/organizations/{org_id}/members")
def get_org_members(org_id: str, db: Session = Depends(get_db)):
    positions = db.query(WDPosition).filter(WDPosition.organization_id == org_id).all()
    members = []
    for pos in positions:
        p = _serialize(pos)
        if pos.worker_id:
            worker = db.query(WDWorker).filter(WDWorker.id == pos.worker_id).first()
            if worker:
                p["worker"] = _serialize(worker)
        members.append(p)
    return _raas_response(members)


# --- Positions ---

@router.get("/positions")
def list_positions(
    organization_id: str | None = None,
    is_filled: bool | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(WDPosition)
    if organization_id:
        query = query.filter(WDPosition.organization_id == organization_id)
    if is_filled is not None:
        query = query.filter(WDPosition.is_filled == is_filled)
    return _raas_response([_serialize(p) for p in query.all()])
