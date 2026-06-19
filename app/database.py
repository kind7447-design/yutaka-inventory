import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 本番は環境変数 DATABASE_URL（Neon の PostgreSQL）を使用。
# 未設定ならローカル開発用 SQLite（プロジェクト直下に固定パスで作成）。
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_SQLITE = "sqlite:///" + os.path.join(_PROJECT_ROOT, "yutaka_inventory.db").replace("\\", "/")
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_SQLITE)

# Render/Neon が postgres:// で渡してくる場合に対応し、psycopg(v3)ドライバを指定
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
