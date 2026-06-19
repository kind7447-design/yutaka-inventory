from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db
from ..models import (
    Item,
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
    UsageReport,
    UsageType,
)
from ..templating import templates

router = APIRouter()


def _user(request, db):
    return current_user(request, db)


@router.get("/history")
def history(request: Request, tab: str = "order", q: str = "", db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    like = f"%{q}%" if q else None
    rows = []
    if tab == "receipt":
        query = db.query(Receipt).join(Item, Item.id == Receipt.item_id)
        if like:
            query = query.filter((Item.item_code.ilike(like)) | (Item.name.ilike(like)))
        rows = query.order_by(Receipt.id.desc()).limit(300).all()
    elif tab == "usage":
        query = db.query(UsageReport).join(Item, Item.id == UsageReport.item_id)
        if like:
            query = query.filter((Item.item_code.ilike(like)) | (Item.name.ilike(like)))
        rows = query.order_by(UsageReport.id.desc()).limit(300).all()
    else:  # order = 依頼履歴
        tab = "order"
        query = (
            db.query(PurchaseOrderLine)
            .join(Item, Item.id == PurchaseOrderLine.item_id)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
        )
        if like:
            query = query.filter((Item.item_code.ilike(like)) | (Item.name.ilike(like)))
        rows = query.order_by(PurchaseOrderLine.id.desc()).limit(300).all()

    return templates.TemplateResponse(
        request, "history.html",
        {"user": user, "tab": tab, "q": q, "rows": rows, "UsageType": UsageType},
    )
