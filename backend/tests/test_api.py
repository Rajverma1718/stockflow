import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "sqlite:///./test_stockflow.db"
if os.path.exists("test_stockflow.db"):
    os.remove("test_stockflow.db")
from fastapi.testclient import TestClient
from app.main import SessionLocal, User, app, password_hash

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"

def test_demo_seed_and_dashboard():
    client.post("/api/demo/seed")
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    assert response.json()["products"] >= 3

def test_auth_register_login():
    email = "test-admin@example.com"
    response = client.post("/api/auth/register", json={"email": email, "password": "correct horse", "name": "Test Admin", "role": "ADMIN"})
    assert response.status_code in (200, 409)
    response = client.post("/api/auth/login", json={"email": email, "password": "correct horse"})
    assert response.status_code == 200
    assert response.json()["token"]

def test_protected_category_and_transfer_flow():
    login = client.post("/api/auth/login", json={"email": "test-admin@example.com", "password": "correct horse"})
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    duplicate_product = client.post("/api/products", json={"sku": "SKU-1001", "name": "Duplicate scanner", "category": "Hardware", "reorder_point": 5, "unit_cost": 1}, headers=headers)
    assert duplicate_product.status_code == 409
    duplicate_sku = client.patch("/api/products/2", json={"sku": "SKU-1001", "name": "Thermal Labels", "category": "Consumables", "reorder_point": 100, "unit_cost": 0.12}, headers=headers)
    assert duplicate_sku.status_code == 409
    category = client.post("/api/categories", json={"name": "Test Category"}, headers=headers)
    assert category.status_code in (200, 409)
    transfer = client.post("/api/transfers", json={"product_id": 1, "from_warehouse_id": 1, "to_warehouse_id": 2, "quantity": 1}, headers=headers)
    assert transfer.status_code == 200
    logs = client.get("/api/audit-logs", headers=headers)
    assert any(log["action"] == "TRANSFER" and log["entity_id"] == str(transfer.json()["id"]) for log in logs.json())
    alerts = client.post("/api/alerts/generate")
    assert alerts.status_code == 200
    assert "created" in alerts.json()

def test_purchase_order_line_and_receiving_flow():
    login = client.post("/api/auth/login", json={"email": "test-admin@example.com", "password": "correct horse"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    empty_order = client.post("/api/purchase-orders", json={"supplier_id": 1, "warehouse_id": 1}, headers=headers)
    assert empty_order.status_code == 200
    assert empty_order.json()["total"] == 0
    empty_approval = client.patch(f"/api/purchase-orders/{empty_order.json()['id']}/approve", headers=headers)
    assert empty_approval.status_code == 400
    po = client.post("/api/purchase-orders", json={"supplier_id": 1, "warehouse_id": 1}, headers=headers)
    assert po.status_code == 200
    line = client.post(f"/api/purchase-orders/{po.json()['id']}/items", json={"product_id": 1, "quantity": 2, "unit_cost": 10}, headers=headers)
    assert line.status_code == 200
    orders = client.get("/api/purchase-orders", headers=headers)
    assert next(order for order in orders.json() if order["id"] == po.json()["id"])["total"] == 20
    blocked = client.post(f"/api/purchase-orders/{po.json()['id']}/receive", json={"item_id": line.json()["id"], "quantity": 2}, headers=headers)
    assert blocked.status_code == 409
    approved = client.patch(f"/api/purchase-orders/{po.json()['id']}/approve", headers=headers)
    assert approved.status_code == 200
    logs = client.get("/api/audit-logs", headers=headers)
    assert any(log["action"] == "APPROVE" and log["entity_id"] == str(po.json()["id"]) for log in logs.json())
    rejected_after_approval = client.patch(f"/api/purchase-orders/{po.json()['id']}/reject", headers=headers)
    assert rejected_after_approval.status_code == 409
    late_item = client.post(f"/api/purchase-orders/{po.json()['id']}/items", json={"product_id": 1, "quantity": 1, "unit_cost": 10}, headers=headers)
    assert late_item.status_code == 409
    inventory_before_over_receipt = client.get("/api/inventory").json()
    over_receipt = client.post(f"/api/purchase-orders/{po.json()['id']}/receive", json={"item_id": line.json()["id"], "quantity": 3}, headers=headers)
    assert over_receipt.status_code == 400
    assert client.get("/api/inventory").json() == inventory_before_over_receipt
    received = client.post(f"/api/purchase-orders/{po.json()['id']}/receive", json={"item_id": line.json()["id"], "quantity": 2}, headers=headers)
    assert received.status_code == 200
    assert received.json()["status"] == "RECEIVED"

    inventory_before = client.get("/api/inventory").json()
    same_warehouse = client.post(
        "/api/transfers",
        json={"product_id": 1, "from_warehouse_id": 1, "to_warehouse_id": 1, "quantity": 1},
        headers=headers,
    )
    zero_quantity = client.post(
        "/api/transfers",
        json={"product_id": 1, "from_warehouse_id": 1, "to_warehouse_id": 2, "quantity": 0},
        headers=headers,
    )
    assert same_warehouse.status_code == 400
    assert zero_quantity.status_code == 400
    assert client.get("/api/inventory").json() == inventory_before

    invalid_destination = client.post(
        "/api/transfers",
        json={"product_id": 1, "from_warehouse_id": 1, "to_warehouse_id": 9999, "quantity": 1},
        headers=headers,
    )
    assert invalid_destination.status_code == 404
    assert client.get("/api/inventory").json() == inventory_before


def test_auth_me_rejects_missing_or_invalid_token():
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_inactive_user_cannot_login():
    session = SessionLocal()
    user = User(
        email="inactive@example.com",
        name="Inactive User",
        password_hash=password_hash("correct horse"),
        role="VIEWER",
        active=False,
    )
    session.add(user)
    session.commit()
    session.close()

    response = client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "correct horse"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
