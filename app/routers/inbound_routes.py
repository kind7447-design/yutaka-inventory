from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db
from ..models import InboundPlan, InboundStatus, Item, Receipt
from ..templating import templates

router = APIRouter()


def _user(request, db):
    return current_user(request, db)


def _parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("/inbound")
def inbound_list(request: Request, status: str = "waiting", db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    q = db.query(InboundPlan)
    if status in (InboundStatus.waiting.value, InboundStatus.received.value):
        q = q.filter(InboundPlan.status == status)
    plans = q.order_by(InboundPlan.plan_date.is_(None), InboundPlan.plan_date, InboundPlan.id).all()
    items = db.query(Item).order_by(Item.item_code).all()
    return templates.TemplateResponse(
        request, "inbound/list.html",
        {"user": user, "plans": plans, "status": status, "items": items},
    )


@router.post("/inbound/new")
def inbound_create(
    request: Request,
    item_code: str = Form(...),
    plan_qty: int = Form(...),
    plan_date: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    item = db.query(Item).filter(Item.item_code == item_code.strip()).first()
    if item and plan_qty > 0:
        db.add(InboundPlan(
            item_id=item.id, plan_qty=plan_qty,
            plan_date=_parse_date(plan_date), status=InboundStatus.waiting,
        ))
        db.commit()
    return RedirectResponse("/inbound", status_code=303)


@router.post("/inbound/{plan_id}/receive")
def inbound_receive(
    plan_id: int,
    request: Request,
    qty: int = Form(...),
    db: Session = Depends(get_db),
):
    """消込：入荷確定 → 在庫を増やし、受入履歴を記録。"""
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    plan = db.query(InboundPlan).get(plan_id)
    if plan and plan.status == InboundStatus.waiting and qty > 0:
        item = db.query(Item).get(plan.item_id)
        db.add(Receipt(
            inbound_plan_id=plan.id, item_id=item.id, qty=qty, operator_id=user.id,
        ))
        item.stock_qty = (item.stock_qty or 0) + qty
        plan.status = InboundStatus.received
        db.commit()
    return RedirectResponse("/inbound", status_code=303)
