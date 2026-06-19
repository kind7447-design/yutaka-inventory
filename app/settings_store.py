from sqlalchemy.orm import Session

from .models import Setting

# 注文依頼書フッター等の既定値（アップ書式 = 林製作所 と同等。設定画面で編集可）
DEFAULTS = {
    "company_name": "株式会社 林製作所",
    "company_address": "群馬県 高崎市 沖町368-1",
    "company_tel": "027-343-1211",
    "company_fax": "027-343-1213",
    "default_deliver_to": "㈱ ユタカ製作所",
}

# 設定画面に出すラベル
LABELS = {
    "company_name": "自社名",
    "company_address": "住所",
    "company_tel": "TEL",
    "company_fax": "FAX",
    "default_deliver_to": "既定の納入場所",
}


def get_all(db: Session) -> dict:
    rows = {s.key: s.value for s in db.query(Setting).all()}
    return {k: rows.get(k, v) for k, v in DEFAULTS.items()}


def get(db: Session, key: str) -> str:
    s = db.query(Setting).get(key)
    return s.value if s and s.value is not None else DEFAULTS.get(key, "")


def set_value(db: Session, key: str, value: str):
    s = db.query(Setting).get(key)
    if s:
        s.value = value
    else:
        db.add(Setting(key=key, value=value))


def ensure_defaults(db: Session):
    changed = False
    for k, v in DEFAULTS.items():
        if not db.query(Setting).get(k):
            db.add(Setting(key=k, value=v))
            changed = True
    if changed:
        db.commit()
