from datetime import date, datetime, timedelta
import base64, hashlib, hmac, json, secrets, smtplib
import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stockflow.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass

class Warehouse(Base):
    __tablename__ = "warehouses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(200))
    stock: Mapped[list["StockLevel"]] = relationship(back_populates="warehouse")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    reorder_point: Mapped[int] = mapped_column(default=10)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    stock: Mapped[list["StockLevel"]] = relationship(back_populates="product")

class StockLevel(Base):
    __tablename__ = "stock_levels"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_id", name="uq_stock_product_warehouse"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[int] = mapped_column(default=0)
    reserved: Mapped[int] = mapped_column(default=0)
    product: Mapped[Product] = relationship(back_populates="stock")
    warehouse: Mapped[Warehouse] = relationship(back_populates="stock")

class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(160))
    lead_time_days: Mapped[int] = mapped_column(default=7)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    status: Mapped[str] = mapped_column(String(30), default="PENDING_APPROVAL")
    total: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DemandEvent(Base):
    __tablename__ = "demand_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    units: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(40), default="VIEWER")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(240), default="")

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[float] = mapped_column(Float)

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    transaction_type: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class StockTransfer(Base):
    __tablename__ = "stock_transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    from_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    to_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

if os.getenv("STOCKFLOW_AUTO_CREATE_TABLES", "true").lower() == "true":
    Base.metadata.create_all(engine)
app = FastAPI(title="StockFlow API", version="0.1.0")
allowed_origins = [origin.strip() for origin in os.getenv("STOCKFLOW_CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"], expose_headers=["X-Request-ID"])

def db():
    session = SessionLocal()
    try: yield session
    finally: session.close()

class WarehouseIn(BaseModel): name: str; location: str
class ProductIn(BaseModel): sku: str; name: str; category: str; reorder_point: int = 10; unit_cost: float = 0
class ProductPatchIn(BaseModel): sku: str; name: str; category: str; reorder_point: int = 10; unit_cost: float = 0
class StockIn(BaseModel): product_id: int; warehouse_id: int; quantity: int; reserved: int = 0
class DemandIn(BaseModel): product_id: int; warehouse_id: int; units: int
class SupplierIn(BaseModel): name: str; email: str; lead_time_days: int = 7
class POIn(BaseModel): supplier_id: int; warehouse_id: int; total: float

@app.get("/health")
def health(): return {"status": "ok", "service": "stockflow-api"}

@app.get("/api/dashboard")
def dashboard(session: Session = Depends(db)):
    products = session.scalars(select(Product)).all()
    stock = session.scalars(select(StockLevel)).all()
    low = [{"sku": s.product.sku, "name": s.product.name, "warehouse": s.warehouse.name, "available": s.quantity-s.reserved, "reorder_point": s.product.reorder_point} for s in stock if s.quantity-s.reserved <= s.product.reorder_point]
    orders = session.scalar(select(func.count(PurchaseOrder.id)).where(PurchaseOrder.status == "PENDING_APPROVAL")) or 0
    return {"products": len(products), "units": sum(s.quantity for s in stock), "low_stock": len(low), "inventory_value": round(sum(s.quantity*s.product.unit_cost for s in stock), 2), "pending_orders": orders, "alerts": low}

@app.get("/api/warehouses")
def warehouses(session: Session = Depends(db)):
    return [{"id": w.id, "name": w.name, "location": w.location, "units": sum(s.quantity for s in w.stock)} for w in session.scalars(select(Warehouse)).all()]

@app.post("/api/warehouses")
def create_warehouse(item: WarehouseIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "MANAGER"}, authorization, session)
    obj = Warehouse(**item.model_dump()); session.add(obj); session.commit(); session.refresh(obj); return obj

@app.get("/api/products")
def products(session: Session = Depends(db)):
    return [{"id": p.id, "sku": p.sku, "name": p.name, "category": p.category, "reorder_point": p.reorder_point, "unit_cost": p.unit_cost} for p in session.scalars(select(Product)).all()]

@app.get("/api/inventory")
def inventory(session: Session = Depends(db)):
    rows = session.scalars(select(StockLevel).order_by(StockLevel.id)).all()
    return [{"id": s.id, "product_id": s.product_id, "warehouse_id": s.warehouse_id, "sku": s.product.sku, "product": s.product.name, "warehouse": s.warehouse.name, "quantity": s.quantity, "reserved": s.reserved, "available": s.quantity - s.reserved, "reorder_point": s.product.reorder_point, "unit_cost": s.product.unit_cost} for s in rows]

@app.post("/api/products")
def create_product(item: ProductIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "MANAGER"}, authorization, session)
    obj = Product(**item.model_dump()); session.add(obj); session.commit(); session.refresh(obj); return obj

@app.patch("/api/products/{product_id}")
def update_product(product_id: int, item: ProductPatchIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN", "MANAGER"}, authorization, session); obj = session.get(Product, product_id)
    if not obj: raise HTTPException(404, "Product not found")
    obj.sku, obj.name, obj.category, obj.reorder_point, obj.unit_cost = item.sku, item.name, item.category, item.reorder_point, item.unit_cost
    audit(session, user, "UPDATE", "Product", str(product_id)); session.commit(); session.refresh(obj); return obj

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN"}, authorization, session); obj = session.get(Product, product_id)
    if not obj: raise HTTPException(404, "Product not found")
    stock_rows = session.scalars(select(StockLevel).where(StockLevel.product_id == product_id)).all()
    if any(row.quantity > 0 or row.reserved > 0 for row in stock_rows):
        raise HTTPException(409, "Cannot delete a product with inventory")
    for row in stock_rows: session.delete(row)
    session.delete(obj); audit(session, user, "DELETE", "Product", str(product_id)); session.commit(); return {"message": "Product deleted"}

@app.post("/api/stock")
def update_stock(item: StockIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "MANAGER"}, authorization, session)
    if item.quantity < 0 or item.reserved < 0 or item.reserved > item.quantity: raise HTTPException(400, "Reserved stock must be between zero and quantity")
    if not session.get(Product, item.product_id) or not session.get(Warehouse, item.warehouse_id): raise HTTPException(404, "Product or warehouse not found")
    obj = session.scalar(select(StockLevel).where(StockLevel.product_id == item.product_id, StockLevel.warehouse_id == item.warehouse_id))
    if obj: obj.quantity, obj.reserved = item.quantity, item.reserved
    else: obj = StockLevel(**item.model_dump()); session.add(obj)
    session.commit(); session.refresh(obj); return obj

@app.get("/api/suppliers")
def suppliers(session: Session = Depends(db)):
    return [{"id": s.id, "name": s.name, "email": s.email, "lead_time_days": s.lead_time_days, "orders": session.scalar(select(func.count(PurchaseOrder.id)).where(PurchaseOrder.supplier_id == s.id)) or 0} for s in session.scalars(select(Supplier)).all()]

@app.post("/api/suppliers")
def create_supplier(item: SupplierIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "PROCUREMENT"}, authorization, session)
    obj = Supplier(**item.model_dump()); session.add(obj); session.commit(); session.refresh(obj); return obj

@app.post("/api/demand")
def record_demand(item: DemandIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "MANAGER"}, authorization, session)
    if item.units <= 0: raise HTTPException(400, "Units must be greater than zero")
    if not session.get(Product, item.product_id) or not session.get(Warehouse, item.warehouse_id): raise HTTPException(404, "Product or warehouse not found")
    event = DemandEvent(**item.model_dump()); session.add(event)
    stock = session.scalar(select(StockLevel).where(StockLevel.product_id == item.product_id, StockLevel.warehouse_id == item.warehouse_id))
    if stock:
        stock.quantity = max(0, stock.quantity - item.units)
    session.commit(); session.refresh(event); return {"id": event.id, "message": "Demand recorded and stock updated"}

@app.get("/api/purchase-orders")
def purchase_orders(session: Session = Depends(db)):
    return [{"id": p.id, "supplier_id": p.supplier_id, "warehouse_id": p.warehouse_id, "status": p.status, "total": p.total, "created_at": p.created_at} for p in session.scalars(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())).all()]

@app.post("/api/purchase-orders")
def create_po(item: POIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "PROCUREMENT"}, authorization, session)
    if item.total <= 0: raise HTTPException(400, "Purchase order total must be greater than zero")
    if not session.get(Supplier, item.supplier_id) or not session.get(Warehouse, item.warehouse_id): raise HTTPException(404, "Supplier or warehouse not found")
    obj = PurchaseOrder(**item.model_dump()); session.add(obj); session.commit(); session.refresh(obj); return obj

@app.patch("/api/purchase-orders/{po_id}/approve")
def approve_po(po_id: int, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "MANAGER"}, authorization, session)
    obj = session.get(PurchaseOrder, po_id)
    if not obj: raise HTTPException(404, "Purchase order not found")
    obj.status = "APPROVED"; session.commit(); session.refresh(obj)
    return {"id": obj.id, "status": obj.status, "message": "Purchase order approved"}

@app.patch("/api/purchase-orders/{po_id}/reject")
def reject_po(po_id: int, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "MANAGER"}, authorization, session)
    obj = session.get(PurchaseOrder, po_id)
    if not obj: raise HTTPException(404, "Purchase order not found")
    obj.status = "REJECTED"; session.commit(); session.refresh(obj)
    return {"id": obj.id, "status": obj.status, "message": "Purchase order rejected"}

@app.get("/api/forecast/{product_id}")
def forecast(product_id: int, days: int = Query(30, ge=7, le=90), session: Session = Depends(db)):
    product = session.get(Product, product_id)
    if not product: raise HTTPException(404, "Product not found")
    events = session.scalars(select(DemandEvent).where(DemandEvent.product_id == product_id).order_by(DemandEvent.recorded_at.desc()).limit(30)).all()
    # Simple explainable moving-average model; replace with a trained model when history is sufficient.
    weekly = [e.units for e in events]
    baseline = sum(weekly) / max(1, len(weekly)) / 7 if weekly else product.reorder_point / 7
    # Trend-adjusted moving average: an explainable lightweight forecasting model that
    # remains dependency-free for local installs and can later be replaced by a worker.
    trend = ((weekly[0] - weekly[-1]) / max(1, len(weekly) - 1) / 7) if len(weekly) > 1 else 0
    daily = round(max(0.1, baseline + trend), 1)
    forecast_units = round(daily * days)
    return {"product_id": product_id, "horizon_days": days, "method": "trend-adjusted moving average" if events else "baseline", "history_points": len(events), "daily_demand": daily, "forecast_units": forecast_units, "recommended_order": round(forecast_units + product.reorder_point)}

@app.post("/api/demo/seed")
def seed(session: Session = Depends(db)):
    if session.scalar(select(Product)): return {"message": "Demo data already exists"}
    w1, w2 = Warehouse(name="Mumbai DC", location="Mumbai, IN"), Warehouse(name="Bengaluru Hub", location="Bengaluru, IN")
    p1, p2, p3 = Product(sku="SKU-1001", name="Wireless Scanner", category="Hardware", reorder_point=20, unit_cost=85), Product(sku="SKU-1002", name="Thermal Labels", category="Consumables", reorder_point=100, unit_cost=0.12), Product(sku="SKU-1003", name="Packing Tape", category="Consumables", reorder_point=50, unit_cost=2.5)
    s1 = Supplier(name="Acme Supplies", email="orders@acme.example", lead_time_days=5); s2 = Supplier(name="Northstar Wholesale", email="sales@northstar.example", lead_time_days=12)
    session.add_all([w1,w2,p1,p2,p3,s1,s2]); session.flush()
    session.add_all([StockLevel(product_id=p1.id, warehouse_id=w1.id, quantity=18), StockLevel(product_id=p2.id, warehouse_id=w1.id, quantity=480), StockLevel(product_id=p3.id, warehouse_id=w2.id, quantity=32), StockLevel(product_id=p1.id, warehouse_id=w2.id, quantity=65)])
    session.commit(); return {"message": "Demo data seeded"}

# --- Identity, workflow, reporting, and audit APIs ---
class AuthIn(BaseModel): email: str; password: str; name: str = "User"; role: str = "VIEWER"
class CategoryIn(BaseModel): name: str; description: str = ""
class POItemIn(BaseModel): product_id: int; quantity: int; unit_cost: float
class ReceiveIn(BaseModel): item_id: int; quantity: int
class TransferIn(BaseModel): product_id: int; from_warehouse_id: int; to_warehouse_id: int; quantity: int

AUTH_SECRET = os.getenv("STOCKFLOW_AUTH_SECRET", "change-this-secret-before-production")
ROLES = {"ADMIN", "MANAGER", "PROCUREMENT", "VIEWER"}
if os.getenv("ENVIRONMENT", "development").lower() == "production" and AUTH_SECRET == "change-this-secret-before-production":
    raise RuntimeError("STOCKFLOW_AUTH_SECRET must be set in production")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

def password_hash(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 180_000)
    return base64.urlsafe_b64encode(salt + digest).decode()

def password_ok(password: str, stored: str) -> bool:
    raw = base64.urlsafe_b64decode(stored.encode())
    return hmac.compare_digest(password_hash(password, raw[:16]), stored)

def make_token(user: User) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"id": user.id, "role": user.role, "exp": int(datetime.utcnow().timestamp()) + 86400}).encode()).decode()
    sig = hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + sig

def current_user(authorization: Optional[str], session: Session) -> Optional[User]:
    if not authorization or not authorization.startswith("Bearer "): return None
    try:
        payload, sig = authorization[7:].split(".", 1)
        if not hmac.compare_digest(hmac.new(AUTH_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest(), sig): return None
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        if data["exp"] < int(datetime.utcnow().timestamp()): return None
        user = session.get(User, int(data["id"]))
        return user if user and user.active else None
    except (ValueError, KeyError, json.JSONDecodeError): return None

def require_role(roles: set[str], authorization: Optional[str], session: Session) -> Optional[User]:
    user = current_user(authorization, session)
    if user and user.role in roles: return user
    raise HTTPException(403, "This action requires one of these roles: " + ", ".join(sorted(roles)))

def audit(session: Session, user: Optional[User], action: str, entity: str, entity_id: str = "", details: str = ""):
    session.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id, details=details))

@app.post("/api/auth/register")
def register(item: AuthIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    if len(item.password) < 8: raise HTTPException(400, "Password must be at least 8 characters")
    existing_users = session.scalar(select(func.count(User.id))) or 0
    if existing_users:
        actor = current_user(authorization, session)
        if not actor or actor.role != "ADMIN": raise HTTPException(403, "Only an admin can create additional users")
    if item.role not in ROLES: raise HTTPException(400, "Invalid role")
    if session.scalar(select(User).where(User.email == item.email.lower())): raise HTTPException(409, "Email already registered")
    user = User(email=item.email.lower(), name=item.name, role="ADMIN" if not existing_users else item.role, password_hash=password_hash(item.password))
    session.add(user); session.commit(); session.refresh(user)
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "token": make_token(user)}

@app.post("/api/auth/login")
def login(item: AuthIn, session: Session = Depends(db)):
    user = session.scalar(select(User).where(User.email == item.email.lower()))
    if not user or not password_ok(item.password, user.password_hash): raise HTTPException(401, "Invalid email or password")
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "token": make_token(user)}

@app.get("/api/auth/me")
def me(authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = current_user(authorization, session)
    if not user: raise HTTPException(401, "Authentication required")
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}

@app.get("/api/categories")
def categories(session: Session = Depends(db)): return session.scalars(select(Category).order_by(Category.name)).all()

@app.post("/api/categories")
def create_category(item: CategoryIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN", "MANAGER"}, authorization, session); obj = Category(**item.model_dump()); session.add(obj); audit(session, user, "CREATE", "Category", item.name); session.commit(); session.refresh(obj); return obj

@app.patch("/api/categories/{category_id}")
def update_category(category_id: int, item: CategoryIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN", "MANAGER"}, authorization, session); obj = session.get(Category, category_id)
    if not obj: raise HTTPException(404, "Category not found")
    obj.name, obj.description = item.name, item.description; audit(session, user, "UPDATE", "Category", str(category_id)); session.commit(); return obj

@app.delete("/api/categories/{category_id}")
def delete_category(category_id: int, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN"}, authorization, session); obj = session.get(Category, category_id)
    if not obj: raise HTTPException(404, "Category not found")
    session.delete(obj); audit(session, user, "DELETE", "Category", str(category_id)); session.commit(); return {"message": "Category deleted"}

@app.post("/api/purchase-orders/{po_id}/items")
def add_po_item(po_id: int, item: POItemIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN", "MANAGER", "PROCUREMENT"}, authorization, session)
    po = session.get(PurchaseOrder, po_id)
    if not po or not session.get(Product, item.product_id): raise HTTPException(404, "Purchase order or product not found")
    if item.quantity <= 0 or item.unit_cost <= 0: raise HTTPException(400, "Quantity and unit cost must be positive")
    line = PurchaseOrderItem(purchase_order_id=po_id, product_id=item.product_id, quantity=item.quantity, unit_cost=item.unit_cost)
    session.add(line); po.total += item.quantity * item.unit_cost; audit(session, user, "ADD_ITEM", "PurchaseOrder", str(po_id)); session.commit(); session.refresh(line); return {"id": line.id, "purchase_order_id": po_id, "product_id": item.product_id, "quantity": item.quantity, "unit_cost": item.unit_cost}

@app.get("/api/purchase-orders/{po_id}/items")
def po_items(po_id: int, session: Session = Depends(db)):
    return session.scalars(select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po_id)).all()

@app.post("/api/purchase-orders/{po_id}/receive")
def receive_po(po_id: int, item: ReceiveIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN", "MANAGER"}, authorization, session); po = session.get(PurchaseOrder, po_id); line = session.get(PurchaseOrderItem, item.item_id)
    if not po or not line or line.purchase_order_id != po_id: raise HTTPException(404, "Purchase order item not found")
    if item.quantity <= 0 or line.received_quantity + item.quantity > line.quantity: raise HTTPException(400, "Received quantity exceeds ordered quantity")
    stock = session.scalar(select(StockLevel).where(StockLevel.product_id == line.product_id, StockLevel.warehouse_id == po.warehouse_id))
    if not stock: stock = StockLevel(product_id=line.product_id, warehouse_id=po.warehouse_id, quantity=0, reserved=0); session.add(stock); session.flush()
    stock.quantity += item.quantity; line.received_quantity += item.quantity
    session.add(InventoryTransaction(product_id=line.product_id, warehouse_id=po.warehouse_id, transaction_type="RECEIPT", quantity=item.quantity, reference=f"PO-{po_id}"))
    if all(i.received_quantity >= i.quantity for i in session.scalars(select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po_id)).all()): po.status = "RECEIVED"
    audit(session, user, "RECEIVE", "PurchaseOrder", str(po_id), str(item.quantity)); session.commit(); return {"message": "Goods received", "status": po.status}

@app.post("/api/transfers")
def transfer_stock(item: TransferIn, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN", "MANAGER"}, authorization, session)
    if item.quantity <= 0 or item.from_warehouse_id == item.to_warehouse_id: raise HTTPException(400, "Invalid transfer")
    source = session.scalar(select(StockLevel).where(StockLevel.product_id == item.product_id, StockLevel.warehouse_id == item.from_warehouse_id))
    if not source or source.quantity - source.reserved < item.quantity: raise HTTPException(400, "Insufficient available stock")
    target = session.scalar(select(StockLevel).where(StockLevel.product_id == item.product_id, StockLevel.warehouse_id == item.to_warehouse_id))
    if not target: target = StockLevel(product_id=item.product_id, warehouse_id=item.to_warehouse_id, quantity=0, reserved=0); session.add(target); session.flush()
    source.quantity -= item.quantity; target.quantity += item.quantity
    transfer = StockTransfer(**item.model_dump()); session.add(transfer)
    session.add_all([InventoryTransaction(product_id=item.product_id, warehouse_id=item.from_warehouse_id, transaction_type="TRANSFER_OUT", quantity=-item.quantity, reference="TRANSFER"), InventoryTransaction(product_id=item.product_id, warehouse_id=item.to_warehouse_id, transaction_type="TRANSFER_IN", quantity=item.quantity, reference="TRANSFER")])
    audit(session, user, "TRANSFER", "StockTransfer", str(transfer.id)); session.commit(); session.refresh(transfer); return {"id": transfer.id, "status": transfer.status}

@app.get("/api/inventory/transactions")
def inventory_transactions(session: Session = Depends(db)):
    return session.scalars(select(InventoryTransaction).order_by(InventoryTransaction.created_at.desc())).all()

@app.get("/api/alerts")
def alerts(session: Session = Depends(db)):
    return session.scalars(select(Alert).where(Alert.resolved == False).order_by(Alert.created_at.desc())).all()

@app.patch("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    user = require_role({"ADMIN", "MANAGER"}, authorization, session); alert = session.get(Alert, alert_id)
    if not alert: raise HTTPException(404, "Alert not found")
    alert.resolved = True; audit(session, user, "RESOLVE", "Alert", str(alert_id)); session.commit(); return {"id": alert.id, "resolved": True}

def send_email_alert(subject: str, message: str):
    host, port, sender, recipient = os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587")), os.getenv("SMTP_FROM"), os.getenv("ALERT_RECIPIENT")
    if not host or not sender or not recipient: return False
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls();
            if os.getenv("SMTP_USER"): server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
            server.sendmail(sender, [recipient], f"Subject: {subject}\n\n{message}")
        return True
    except (OSError, smtplib.SMTPException): return False

@app.post("/api/alerts/generate")
def generate_alerts(session: Session = Depends(db)):
    created = 0
    for s in session.scalars(select(StockLevel)).all():
        if s.quantity - s.reserved <= s.product.reorder_point:
            exists = session.scalar(select(Alert).where(Alert.resolved == False, Alert.kind == "LOW_STOCK", Alert.message.contains(s.product.sku)))
            if not exists:
                message = f"{s.product.sku} is low at {s.warehouse.name} ({s.quantity - s.reserved} available)"
                session.add(Alert(kind="LOW_STOCK", severity="WARNING", message=message)); created += 1
                send_email_alert("StockFlow low-stock alert", message)
    session.commit(); return {"created": created, "email_configured": bool(os.getenv("SMTP_HOST") and os.getenv("ALERT_RECIPIENT"))}

@app.get("/api/audit-logs")
def audit_logs(authorization: Optional[str] = Header(None), session: Session = Depends(db)):
    require_role({"ADMIN", "MANAGER"}, authorization, session)
    return session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).all()
