"""初期データ投入: 管理者ユーザーとサンプル品目。
実行: python seed.py
"""
from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import AppUser, Item, Kind, Role

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if not db.query(AppUser).filter(AppUser.login_id == "admin").first():
    db.add(AppUser(
        login_id="admin", name="管理者",
        password_hash=hash_password("admin"), role=Role.admin, active=True,
    ))
    print("admin ユーザーを作成 (ID: admin / PW: admin)")

samples = [
    ("USC1549G11", Kind.chotatsu, "箱組立", "USC15846 照合4", "座"),
    ("USE142598-P4", Kind.shikyu, "レール", "SS", ""),
]
for code, kind, name, material, cat in samples:
    if not db.query(Item).filter(Item.item_code == code).first():
        db.add(Item(item_code=code, kind=kind, name=name, material=material,
                    category=cat, unit="個", stock_qty=0))
        print(f"サンプル品目を作成: {code}")

db.commit()
db.close()
print("完了")
