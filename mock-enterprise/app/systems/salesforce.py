"""Mock Salesforce REST API.

Real API shape: GET /services/data/v59.0/sobjects/Account
Response: {"records": [...], "totalSize": N, "done": true}
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SFAccount, SFContact, SFOpportunity, SFUser

router = APIRouter(prefix="/api/sfdc", tags=["Salesforce"])


def _serialize(obj, fields=None):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    if fields:
        d = {k: v for k, v in d.items() if k in fields}
    return d


def _soql_response(records: list) -> dict:
    """Mimic Salesforce SOQL response shape."""
    return {"totalSize": len(records), "done": True, "records": records}


# --- Accounts ---

@router.get("/accounts")
def list_accounts(
    account_type: str | None = None,
    status: str = "Active",
    q: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SFAccount).filter(SFAccount.status == status)
    if account_type:
        query = query.filter(SFAccount.account_type == account_type)
    if q:
        query = query.filter(SFAccount.name.ilike(f"%{q}%"))
    accounts = query.all()
    return _soql_response([_serialize(a) for a in accounts])


@router.get("/accounts/{account_id}")
def get_account(account_id: str, db: Session = Depends(get_db)):
    account = db.query(SFAccount).filter(SFAccount.id == account_id).first()
    if not account:
        return {"error": "NOT_FOUND", "message": f"Account {account_id} not found"}
    result = _serialize(account)
    result["Contacts"] = _soql_response(
        [_serialize(c) for c in db.query(SFContact).filter(SFContact.account_id == account_id).all()]
    )
    result["Opportunities"] = _soql_response(
        [_serialize(o) for o in db.query(SFOpportunity).filter(SFOpportunity.account_id == account_id).all()]
    )
    return result


# --- Contacts ---

@router.get("/contacts")
def list_contacts(
    account_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SFContact)
    if account_id:
        query = query.filter(SFContact.account_id == account_id)
    return _soql_response([_serialize(c) for c in query.all()])


@router.get("/contacts/{contact_id}")
def get_contact(contact_id: str, db: Session = Depends(get_db)):
    contact = db.query(SFContact).filter(SFContact.id == contact_id).first()
    if not contact:
        return {"error": "NOT_FOUND"}
    return _serialize(contact)


# --- Opportunities ---

@router.get("/opportunities")
def list_opportunities(
    account_id: str | None = None,
    stage: str | None = None,
    contract_type: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SFOpportunity)
    if account_id:
        query = query.filter(SFOpportunity.account_id == account_id)
    if stage:
        query = query.filter(SFOpportunity.stage == stage)
    if contract_type:
        query = query.filter(SFOpportunity.contract_type == contract_type)
    return _soql_response([_serialize(o) for o in query.all()])


@router.get("/opportunities/{opp_id}")
def get_opportunity(opp_id: str, db: Session = Depends(get_db)):
    opp = db.query(SFOpportunity).filter(SFOpportunity.id == opp_id).first()
    if not opp:
        return {"error": "NOT_FOUND"}
    return _serialize(opp)


# --- Users ---

@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    return _soql_response([_serialize(u) for u in db.query(SFUser).all()])
