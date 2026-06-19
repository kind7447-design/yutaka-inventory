import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


class Kind(str, enum.Enum):
    shikyu = "shikyu"        # 支給品
    chotatsu = "chotatsu"    # 調達品


class Role(str, enum.Enum):
    admin = "admin"
    staff = "staff"


class POKind(str, enum.Enum):
    chotatsu = "chotatsu"          # 調達発注
    shikyu_prep = "shikyu_prep"    # 客先準備分


class POStatus(str, enum.Enum):
    open = "open"
    received = "received"
    closed = "closed"


class InboundStatus(str, enum.Enum):
    waiting = "waiting"
    received = "received"


class UsageType(str, enum.Enum):
    used = "used"        # 使用
    defect = "defect"    # 仕損


class AppUser(Base):
    __tablename__ = "app_user"

    id = Column(Integer, primary_key=True)
    login_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(Role), default=Role.staff, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Item(Base):
    __tablename__ = "item"

    id = Column(Integer, primary_key=True)
    item_code = Column(String(64), unique=True, nullable=False, index=True)  # 固有番号（英数記号）
    kind = Column(Enum(Kind), nullable=False)
    name = Column(String(255), nullable=False)        # 製品名（日本語可）
    material = Column(String(128))                    # 材質/部品番号
    category = Column(String(64))                     # 種類
    thickness = Column(String(64))                    # 板厚
    size = Column(String(64))                         # サイズ
    unit = Column(String(16), default="個")           # 単位
    stock_qty = Column(Integer, default=0, nullable=False)
    supplier = Column(String(255))                    # 発注先/支給元
    note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PurchaseOrder(Base):
    __tablename__ = "purchase_order"

    id = Column(Integer, primary_key=True)
    order_no = Column(String(64), index=True)
    order_date = Column(Date)
    kind = Column(Enum(POKind), nullable=False)
    supplier = Column(String(255))
    deliver_to = Column(String(255))
    status = Column(Enum(POStatus), default=POStatus.open, nullable=False)
    created_by = Column(Integer, ForeignKey("app_user.id"))
    created_at = Column(DateTime, server_default=func.now())

    lines = relationship("PurchaseOrderLine", back_populates="po", cascade="all, delete-orphan")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_line"

    id = Column(Integer, primary_key=True)
    po_id = Column(Integer, ForeignKey("purchase_order.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("item.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2))   # 税抜
    due_date = Column(Date)
    repeat_flag = Column(Boolean, default=False)
    note = Column(Text)

    po = relationship("PurchaseOrder", back_populates="lines")
    item = relationship("Item")


class InboundPlan(Base):
    __tablename__ = "inbound_plan"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("item.id"), nullable=False)
    po_line_id = Column(Integer, ForeignKey("purchase_order_line.id"))
    plan_qty = Column(Integer, nullable=False)
    plan_date = Column(Date)
    status = Column(Enum(InboundStatus), default=InboundStatus.waiting, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item")


class Receipt(Base):
    __tablename__ = "receipt"

    id = Column(Integer, primary_key=True)
    inbound_plan_id = Column(Integer, ForeignKey("inbound_plan.id"))
    item_id = Column(Integer, ForeignKey("item.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    received_at = Column(DateTime, server_default=func.now())
    operator_id = Column(Integer, ForeignKey("app_user.id"))

    item = relationship("Item")
    operator = relationship("AppUser")


class UsageReport(Base):
    __tablename__ = "usage_report"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("item.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    report_type = Column(Enum(UsageType), default=UsageType.used, nullable=False)
    reported_at = Column(DateTime, server_default=func.now())
    operator_id = Column(Integer, ForeignKey("app_user.id"))
    note = Column(Text)

    item = relationship("Item")
    operator = relationship("AppUser")


class Setting(Base):
    """会社情報など、画面から編集できる key/value 設定。"""
    __tablename__ = "setting"

    key = Column(String(64), primary_key=True)
    value = Column(Text)


class Drawing(Base):
    """図面ファイル。Render無料はディスク非永続のため、DB(bytea)に保存する。"""
    __tablename__ = "drawing"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("item.id"), nullable=False)
    filename = Column(String(255))
    content_type = Column(String(128))
    data = Column(LargeBinary)
    uploaded_at = Column(DateTime, server_default=func.now())

    item = relationship("Item", backref="drawings")
