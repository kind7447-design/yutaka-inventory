from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db
from ..models import InboundPlan, Item, Kind, PurchaseOrderLine, Receipt, UsageReport
from ..qr import qr_data_uri
from ..templating import templates

router = APIRouter()


def _require_login(request: Request, db: Session):
    user = current_user(request, db)
    return user


@router.get("/items")
def item_list(request: Request, q: str = "", kind: str = "", db: Session = Depends(get_db)):
    user = _require_login(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    query = db.query(Item)
    if kind in (Kind.shikyu.value, Kind.chotatsu.value):
        query = query.filter(Item.kind == kind)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Item.item_code.ilike(like), Item.name.ilike(like)))
    items = query.order_by(Item.item_code).all()
    return templates.TemplateResponse(
        request, "items/list.html",
        {"user": user, "items": items, "q": q, "kind": kind, "Kind": Kind},
    )


@router.get("/items/new")
def item_new(request: Request, db: Session = Depends(get_db)):
    user = _require_login(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request, "items/form.html",
        {"user": user, "item": None, "Kind": Kind, "error": None},
    )


@router.post("/items/new")
def item_create(
    request: Request,
    item_code: str = Form(...),
    kind: str = Form(...),
    name: str = Form(...),
    material: str = Form(""),
    category: str = Form(""),
    thickness: str = Form(""),
    size: str = Form(""),
    unit: str = Form("個"),
    supplier: str = Form(""),
    note: str = Form(""),
    stock_qty: int = Form(0),
    db: Session = Depends(get_db),
):
    user = _require_login(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    item_code = item_code.strip()
    if db.query(Item).filter(Item.item_code == item_code).first():
        return templates.TemplateResponse(
            request, "items/form.html",
            {
                "user": user, "item": None, "Kind": Kind,
                "error": f"固有番号 {item_code} は既に登録済みです",
            },
            status_code=400,
        )

    item = Item(
        item_code=item_code, kind=kind, name=name.strip(), material=material,
        category=category, thickness=thickness, size=size, unit=unit or "個",
        supplier=supplier, note=note, stock_qty=stock_qty,
    )
    db.add(item)
    db.commit()
    return RedirectResponse("/items", status_code=303)


@router.get("/items/{item_id}/edit")
def item_edit(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_login(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    item = db.query(Item).get(item_id)
    if not item:
        return RedirectResponse("/items", status_code=303)
    return templates.TemplateResponse(
        request, "items/form.html",
        {"user": user, "item": item, "Kind": Kind, "error": None},
    )


@router.post("/items/{item_id}/edit")
def item_update(
    item_id: int,
    request: Request,
    item_code: str = Form(...),
    kind: str = Form(...),
    name: str = Form(...),
    material: str = Form(""),
    category: str = Form(""),
    thickness: str = Form(""),
    size: str = Form(""),
    unit: str = Form("個"),
    supplier: str = Form(""),
    note: str = Form(""),
    stock_qty: int = Form(0),
    db: Session = Depends(get_db),
):
    user = _require_login(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    item = db.query(Item).get(item_id)
    if not item:
        return RedirectResponse("/items", status_code=303)

    item_code = item_code.strip()
    dup = db.query(Item).filter(Item.item_code == item_code, Item.id != item_id).first()
    if dup:
        return templates.TemplateResponse(
            request, "items/form.html",
            {"user": user, "item": item, "Kind": Kind,
             "error": f"固有番号 {item_code} は既に登録済みです"},
            status_code=400,
        )

    item.item_code = item_code
    item.kind = kind
    item.name = name.strip()
    item.material = material
    item.category = category
    item.thickness = thickness
    item.size = size
    item.unit = unit or "個"
    item.supplier = supplier
    item.note = note
    item.stock_qty = stock_qty
    db.commit()
    return RedirectResponse("/items", status_code=303)


@router.post("/items/{item_id}/delete")
def item_delete(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_login(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    item = db.query(Item).get(item_id)
    if not item:
        return RedirectResponse("/items", status_code=303)

    used = (
        db.query(Receipt).filter(Receipt.item_id == item_id).first()
        or db.query(UsageReport).filter(UsageReport.item_id == item_id).first()
        or db.query(PurchaseOrderLine).filter(PurchaseOrderLine.item_id == item_id).first()
        or db.query(InboundPlan).filter(InboundPlan.item_id == item_id).first()
    )
    if used:
        items = db.query(Item).order_by(Item.item_code).all()
        return templates.TemplateResponse(
            request, "items/list.html",
            {"user": user, "items": items, "q": "", "kind": "",
             "error": f"「{item.item_code}」には履歴があるため削除できません"},
            status_code=400,
        )

    db.delete(item)
    db.commit()
    return RedirectResponse("/items", status_code=303)


@router.get("/qr/print")
def qr_print(request: Request, ids: str = "", db: Session = Depends(get_db)):
    """選択した品目のQRをA5・2×2面付けで印刷。ids=カンマ区切りのitem.id"""
    user = _require_login(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    items = []
    if id_list:
        rows = db.query(Item).filter(Item.id.in_(id_list)).all()
        order = {i: n for n, i in enumerate(id_list)}
        rows.sort(key=lambda r: order.get(r.id, 9999))
        items = [{"item_code": r.item_code, "name": r.name, "qr": qr_data_uri(r.item_code)} for r in rows]

    # 4枚ごとのページに分割
    pages = [items[i:i + 4] for i in range(0, len(items), 4)] or [[]]
    return templates.TemplateResponse(
        request, "qr_print.html", {"pages": pages}
    )
