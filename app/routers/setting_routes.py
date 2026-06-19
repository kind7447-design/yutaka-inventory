from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db
from ..settings_store import LABELS, get_all, set_value
from ..templating import templates

router = APIRouter()


@router.get("/settings")
def settings_form(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request, "settings.html",
        {"user": user, "values": get_all(db), "labels": LABELS, "saved": False},
    )


@router.post("/settings")
async def settings_save(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    for key in LABELS:
        if key in form:
            set_value(db, key, (form.get(key) or "").strip())
    db.commit()
    return templates.TemplateResponse(
        request, "settings.html",
        {"user": user, "values": get_all(db), "labels": LABELS, "saved": True},
    )
