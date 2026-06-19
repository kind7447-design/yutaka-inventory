import os

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .auth import current_user, hash_password
from .database import Base, SessionLocal, engine, get_db
from .models import AppUser, Role
from .routers import (
    auth_routes,
    drawing_routes,
    history_routes,
    inbound_routes,
    item_routes,
    order_routes,
    setting_routes,
    usage_routes,
    user_routes,
)
from .settings_store import ensure_defaults
from .templating import templates

# 開発用: 起動時にテーブル作成（本番はAlembic想定）
Base.metadata.create_all(bind=engine)

# 設定の既定値＋初回起動時の管理者を投入
_db = SessionLocal()
try:
    ensure_defaults(_db)
    # ユーザーが1人もいなければ管理者を自動作成（Render無料はShell不可のため）
    if not _db.query(AppUser).first():
        _db.add(AppUser(
            login_id="admin",
            name="管理者",
            password_hash=hash_password(os.getenv("ADMIN_PASSWORD", "admin")),
            role=Role.admin,
            active=True,
        ))
        _db.commit()
finally:
    _db.close()

app = FastAPI(title="ユタカ製作所 在庫管理")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.include_router(auth_routes.router)
app.include_router(item_routes.router)
app.include_router(order_routes.router)
app.include_router(inbound_routes.router)
app.include_router(usage_routes.router)
app.include_router(history_routes.router)
app.include_router(setting_routes.router)
app.include_router(drawing_routes.router)
app.include_router(user_routes.router)


@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "home.html", {"user": user})
