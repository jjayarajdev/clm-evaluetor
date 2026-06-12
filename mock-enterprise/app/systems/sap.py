"""Mock SAP S/4HANA OData API.

Real API shape: GET /sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder
Response: {"d": {"results": [...], "__count": N}}
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SAPPurchaseOrder, SAPPOLineItem, SAPInvoice, SAPPayment

router = APIRouter(prefix="/api/sap", tags=["SAP"])


def _serialize(obj):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


def _odata_response(results: list) -> dict:
    """Mimic SAP OData response shape."""
    return {"d": {"results": results, "__count": str(len(results))}}


# --- Purchase Orders ---

@router.get("/purchase-orders")
def list_purchase_orders(
    vendor_code: str | None = None,
    status: str | None = None,
    contract_reference: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SAPPurchaseOrder)
    if vendor_code:
        query = query.filter(SAPPurchaseOrder.vendor_code == vendor_code)
    if status:
        query = query.filter(SAPPurchaseOrder.status == status)
    if contract_reference:
        query = query.filter(SAPPurchaseOrder.contract_reference == contract_reference)
    return _odata_response([_serialize(po) for po in query.all()])


@router.get("/purchase-orders/{po_id}")
def get_purchase_order(po_id: str, db: Session = Depends(get_db)):
    po = db.query(SAPPurchaseOrder).filter(SAPPurchaseOrder.id == po_id).first()
    if not po:
        return {"error": {"code": "404", "message": "Purchase Order not found"}}
    result = _serialize(po)
    result["to_PurchaseOrderItem"] = {
        "results": [_serialize(li) for li in db.query(SAPPOLineItem).filter(SAPPOLineItem.po_id == po_id).all()]
    }
    return {"d": result}


@router.get("/purchase-orders/{po_id}/items")
def get_po_items(po_id: str, db: Session = Depends(get_db)):
    items = db.query(SAPPOLineItem).filter(SAPPOLineItem.po_id == po_id).all()
    return _odata_response([_serialize(li) for li in items])


# --- Invoices ---

@router.get("/invoices")
def list_invoices(
    vendor_name: str | None = None,
    status: str | None = None,
    po_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SAPInvoice)
    if vendor_name:
        query = query.filter(SAPInvoice.vendor_name.ilike(f"%{vendor_name}%"))
    if status:
        query = query.filter(SAPInvoice.status == status)
    if po_id:
        query = query.filter(SAPInvoice.po_id == po_id)
    return _odata_response([_serialize(inv) for inv in query.all()])


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str, db: Session = Depends(get_db)):
    inv = db.query(SAPInvoice).filter(SAPInvoice.id == invoice_id).first()
    if not inv:
        return {"error": {"code": "404", "message": "Invoice not found"}}
    return {"d": _serialize(inv)}


@router.get("/invoices/overdue")
def list_overdue_invoices(db: Session = Depends(get_db)):
    invoices = db.query(SAPInvoice).filter(SAPInvoice.status == "Overdue").all()
    return _odata_response([_serialize(inv) for inv in invoices])


# --- Payments ---

@router.get("/payments")
def list_payments(
    vendor_code: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SAPPayment)
    if vendor_code:
        query = query.filter(SAPPayment.vendor_code == vendor_code)
    return _odata_response([_serialize(p) for p in query.order_by(SAPPayment.payment_date.desc()).all()])


@router.get("/vendor-balance/{vendor_code}")
def get_vendor_balance(vendor_code: str, db: Session = Depends(get_db)):
    """Summarize open invoices and payments for a vendor."""
    from sqlalchemy import func
    open_invoices = db.query(
        func.count(SAPInvoice.id).label("count"),
        func.sum(SAPInvoice.amount).label("total"),
    ).join(SAPPurchaseOrder).filter(
        SAPPurchaseOrder.vendor_code == vendor_code,
        SAPInvoice.status.in_(["Pending", "Approved", "Overdue"]),
    ).first()
    paid = db.query(
        func.sum(SAPPayment.amount).label("total"),
    ).filter(SAPPayment.vendor_code == vendor_code).first()

    return {
        "vendor_code": vendor_code,
        "open_invoices": open_invoices.count or 0,
        "outstanding_amount": float(open_invoices.total or 0),
        "total_paid": float(paid.total or 0),
        "currency": "USD",
    }
