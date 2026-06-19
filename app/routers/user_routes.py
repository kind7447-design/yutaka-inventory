from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import current_user, hash_password, verify_password
from ..database import get_db
from ..models import AppUser, Role
from ..templating import templates

router = APIRouter()


def _require_admin(request: Request, db: Session):
    user = current_user(request, db)
    if not user:
        return None, RedirectResponse("/login", status_code=303)
    if user.role != Role.admin:
        return None, RedirectResponse("/", status_code=303)
    return user, None


# ---- 管理者：ユーザー管理 ----
@router.get("/users")
def user_list(request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    users = db.query(AppUser).order_by(AppUser.id).all()
    return templates.TemplateResponse(
        request, "users/list.html", {"user": user, "users": users, "Role": Role},
    )


@router.get("/users/new")
def user_new(request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request, "users/form.html",
        {"user": user, "target": None, "Role": Role, "error": None},
    )


@router.post("/users/new")
def user_create(
    request: Request,
    login_id: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    role: str = Form("staff"),
    db: Session = Depends(get_db),
):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    login_id = login_id.strip()
    if not login_id or not password:
        return templates.TemplateResponse(
            request, "users/form.html",
            {"user": user, "target": None, "Role": Role, "error": "ログインIDとパスワードは必須です"},
            status_code=400,
        )
    if db.query(AppUser).filter(AppUser.login_id == login_id).first():
        return templates.TemplateResponse(
            request, "users/form.html",
            {"user": user, "target": None, "Role": Role, "error": f"ログインID {login_id} は既に使われています"},
            status_code=400,
        )
    db.add(AppUser(
        login_id=login_id, name=name.strip() or login_id,
        password_hash=hash_password(password),
        role=Role.admin if role == "admin" else Role.staff, active=True,
    ))
    db.commit()
    return RedirectResponse("/users", status_code=303)


@router.get("/users/{user_id}/edit")
def user_edit(user_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    target = db.query(AppUser).get(user_id)
    if not target:
        return RedirectResponse("/users", status_code=303)
    return templates.TemplateResponse(
        request, "users/form.html",
        {"user": user, "target": target, "Role": Role, "error": None},
    )


@router.post("/users/{user_id}/edit")
def user_update(
    user_id: int,
    request: Request,
    name: str = Form(...),
    role: str = Form("staff"),
    active: str = Form(None),
    db: Session = Depends(get_db),
):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    target = db.query(AppUser).get(user_id)
    if not target:
        return RedirectResponse("/users", status_code=303)
    target.name = name.strip() or target.login_id
    target.role = Role.admin if role == "admin" else Role.staff
    new_active = active is not None
    # 自分自身を無効化・降格して締め出すのを防ぐ
    if target.id == user.id:
        target.role = Role.admin
        new_active = True
    target.active = new_active
    db.commit()
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/reset-password")
def user_reset_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user, redirect = _require_admin(request, db)
    if redirect:
        return redirect
    target = db.query(AppUser).get(user_id)
    if target and new_password:
        target.password_hash = hash_password(new_password)
        db.commit()
    return RedirectResponse("/users", status_code=303)


# ---- 全ユーザー：自分のパスワード変更 ----
@router.get("/password")
def password_form(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request, "users/password.html", {"user": user, "error": None, "saved": False},
    )


@router.post("/password")
def password_change(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    err = None
    if not verify_password(current_password, user.password_hash):
        err = "現在のパスワードが違います"
    elif len(new_password) < 4:
        err = "新しいパスワードは4文字以上にしてください"
    elif new_password != confirm_password:
        err = "新しいパスワード（確認）が一致しません"
    if err:
        return templates.TemplateResponse(
            request, "users/password.html", {"user": user, "error": err, "saved": False},
            status_code=400,
        )
    user.password_hash = hash_password(new_password)
    db.commit()
    return templates.TemplateResponse(
        request, "users/password.html", {"user": user, "error": None, "saved": True},
    )
