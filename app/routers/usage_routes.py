from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db
from ..models import Item, UsageReport, UsageType
from ..templating import templates

router = APIRouter()


def _user(request, db):
    return current_user(request, db)


@router.get("/usage")
def usage_form(request: Request, code: str = "", db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    items = db.query(Item).order_by(Item.item_code).all()
    recent = (
        db.query(UsageReport).order_by(UsageReport.id.desc()).limit(10).all()
    )
    return templates.TemplateResponse(
        request, "usage/form.html",
        {"user": user, "items": items, "recent": recent, "UsageType": UsageType, "code": code, "error": None},
    )


@router.post("/usage")
def usage_create(
    request: Request,
    item_code: str = Form(...),
    qty: int = Form(...),
    report_type: str = Form("used"),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    item = db.query(Item).filter(Item.item_code == item_code.strip()).first()
    if not item or qty <= 0:
        items = db.query(Item).order_by(Item.item_code).all()
        recent = db.query(UsageReport).order_by(UsageReport.id.desc()).limit(10).all()
        return templates.TemplateResponse(
            request, "usage/form.html",
            {"user": user, "items": items, "recent": recent, "UsageType": UsageType,
             "code": item_code, "error": "品目と数量を正しく入力してください"},
            status_code=400,
        )
    rtype = UsageType.defect if report_type == "defect" else UsageType.used
    db.add(UsageReport(
        item_id=item.id, qty=qty, report_type=rtype, operator_id=user.id, note=note,
    ))
    item.stock_qty = (item.stock_qty or 0) - qty  # 在庫を減らす（マイナス許容）
    db.commit()
    return RedirectResponse("/usage", status_code=303)
