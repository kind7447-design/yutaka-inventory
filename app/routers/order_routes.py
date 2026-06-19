from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db
from ..models import (
    Drawing,
    InboundPlan,
    InboundStatus,
    Item,
    Kind,
    POKind,
    PurchaseOrder,
    PurchaseOrderLine,
)
from ..pdf import order_sheet_pdf, process_sheet_pdf
from ..settings_store import get_all
from ..templating import templates

router = APIRouter()


def _user(request, db):
    return current_user(request, db)


def _next_order_no(db: Session) -> str:
    nums = []
    for (no,) in db.query(PurchaseOrder.order_no).all():
        if no and no.isdigit():
            nums.append(int(no))
    return str((max(nums) + 1) if nums else 1001)


def _parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


@router.get("/orders")
def order_list(request: Request, kind: str = "", db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    q = db.query(PurchaseOrder)
    if kind in (POKind.chotatsu.value, POKind.shikyu_prep.value):
        q = q.filter(PurchaseOrder.kind == kind)
    orders = q.order_by(PurchaseOrder.id.desc()).all()
    return templates.TemplateResponse(
        request, "orders/list.html",
        {"user": user, "orders": orders, "kind": kind, "POKind": POKind},
    )


@router.get("/orders/new")
def order_new(request: Request, kind: str = "chotatsu", db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if kind not in (POKind.chotatsu.value, POKind.shikyu_prep.value):
        kind = POKind.chotatsu.value
    # 調達発注は調達品、客先準備分は支給品を選択肢に
    item_kind = Kind.chotatsu if kind == POKind.chotatsu.value else Kind.shikyu
    items = db.query(Item).filter(Item.kind == item_kind).order_by(Item.item_code).all()
    settings = get_all(db)
    return templates.TemplateResponse(
        request, "orders/form.html",
        {
            "user": user, "kind": kind, "POKind": POKind, "items": items,
            "order_no": _next_order_no(db), "today": date.today().isoformat(),
            "default_deliver_to": settings.get("default_deliver_to", ""),
            "error": None,
        },
    )


@router.post("/orders/new")
async def order_create(request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    form = await request.form()
    kind = form.get("kind", POKind.chotatsu.value)
    order_no = (form.get("order_no") or "").strip()
    order_date = _parse_date(form.get("order_date"))
    supplier = (form.get("supplier") or "").strip()
    deliver_to = (form.get("deliver_to") or "").strip()

    codes = form.getlist("item_code")
    qtys = form.getlist("qty")
    prices = form.getlist("unit_price")
    dues = form.getlist("due_date")
    repeats = form.getlist("repeat")  # checkbox: value=行index
    notes = form.getlist("note")

    repeat_set = set(repeats)

    po = PurchaseOrder(
        order_no=order_no, order_date=order_date, kind=kind,
        supplier=supplier, deliver_to=deliver_to, created_by=user.id,
    )

    line_count = 0
    for i, code in enumerate(codes):
        code = (code or "").strip()
        qty_s = qtys[i] if i < len(qtys) else ""
        if not code or not (qty_s or "").strip():
            continue
        item = db.query(Item).filter(Item.item_code == code).first()
        if not item:
            continue
        try:
            qty = int(qty_s)
        except ValueError:
            continue
        if qty <= 0:
            continue
        price = None
        if i < len(prices) and (prices[i] or "").strip():
            try:
                price = float(prices[i])
            except ValueError:
                price = None
        due = _parse_date(dues[i]) if i < len(dues) else None
        note = notes[i] if i < len(notes) else ""
        line = PurchaseOrderLine(
            item=item, qty=qty, unit_price=price, due_date=due,
            repeat_flag=(str(i) in repeat_set), note=note,
        )
        po.lines.append(line)
        line_count += 1

    if line_count == 0:
        item_kind = Kind.chotatsu if kind == POKind.chotatsu.value else Kind.shikyu
        items = db.query(Item).filter(Item.kind == item_kind).order_by(Item.item_code).all()
        return templates.TemplateResponse(
            request, "orders/form.html",
            {
                "user": user, "kind": kind, "POKind": POKind, "items": items,
                "order_no": order_no, "today": date.today().isoformat(),
                "default_deliver_to": deliver_to, "error": "明細を1件以上入力してください",
            },
            status_code=400,
        )

    db.add(po)
    db.flush()  # po.id / line.id 確定

    # 発注した分の入荷予定を自動生成（消込待ち）
    for line in po.lines:
        db.add(InboundPlan(
            item_id=line.item_id, po_line_id=line.id,
            plan_qty=line.qty, plan_date=line.due_date, status=InboundStatus.waiting,
        ))

    db.commit()
    return RedirectResponse(f"/orders/{po.id}", status_code=303)


@router.get("/orders/{po_id}")
def order_detail(po_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    po = db.query(PurchaseOrder).get(po_id)
    if not po:
        return RedirectResponse("/orders", status_code=303)
    return templates.TemplateResponse(
        request, "orders/detail.html",
        {"user": user, "po": po, "POKind": POKind},
    )


@router.get("/orders/{po_id}/order-sheet.pdf")
def order_sheet(po_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    po = db.query(PurchaseOrder).get(po_id)
    if not po:
        return RedirectResponse("/orders", status_code=303)
    lines = [(ln, ln.item) for ln in po.lines]
    pdf = order_sheet_pdf(po, lines, get_all(db))
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="order_{po.order_no or po.id}.pdf"'},
    )


@router.get("/orders/{po_id}/process-sheet.pdf")
def process_sheet(po_id: int, request: Request, db: Session = Depends(get_db)):
    user = _user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    po = db.query(PurchaseOrder).get(po_id)
    if not po:
        return RedirectResponse("/orders", status_code=303)
    lines = [(ln, ln.item) for ln in po.lines]
    # 各品目の最新図面
    drawings = {}
    for _, item in lines:
        d = (
            db.query(Drawing).filter(Drawing.item_id == item.id)
            .order_by(Drawing.id.desc()).first()
        )
        if d:
            drawings[item.id] = d
    pdf = process_sheet_pdf(lines, drawings, get_all(db))
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="process_{po.order_no or po.id}.pdf"'},
    )
