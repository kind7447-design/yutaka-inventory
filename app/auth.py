import bcrypt
from fastapi import Request
from sqlalchemy.orm import Session

from .models import AppUser


def hash_password(password: str) -> str:
    # bcrypt は72バイト上限。パスワードは事前に切り詰める。
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    pw = password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw, password_hash.encode("ascii"))
    except ValueError:
        return False


def current_user(request: Request, db: Session):
    uid = request.session.get("uid")
    if not uid:
        return None
    return db.query(AppUser).filter(AppUser.id == uid, AppUser.active == True).first()  # noqa: E712
