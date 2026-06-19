from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db
from ..models import Drawing, Item
from ..templating import templates

router = APIRouter()


@router.get("/items/{item_id}/drawings")
def drawing_list(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    item = db.query(Item).get(item_id)
    if not item:
        return RedirectResponse("/items", status_code=303)
    drawings = db.query(Drawing).filter(Drawing.item_id == item_id).order_by(Drawing.id.desc()).all()
    return templates.TemplateResponse(
        request, "drawings.html", {"user": user, "item": item, "drawings": drawings},
    )


@router.post("/items/{item_id}/drawings")
async def drawing_upload(
    item_id: int, request: Request,
    file: UploadFile = File(...), db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    item = db.query(Item).get(item_id)
    if item and file and file.filename:
        data = await file.read()
        db.add(Drawing(
            item_id=item_id, filename=file.filename,
            content_type=file.content_type or "application/octet-stream", data=data,
        ))
        db.commit()
    return RedirectResponse(f"/items/{item_id}/drawings", status_code=303)


@router.get("/drawings/{drawing_id}")
def drawing_view(drawing_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    d = db.query(Drawing).get(drawing_id)
    if not d:
        return RedirectResponse("/items", status_code=303)
    return Response(
        content=d.data, media_type=d.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{d.filename or d.id}"'},
    )
