import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "sqlite:///./test_stockflow.db"
if os.path.exists("test_stockflow.db"):
    os.remove("test_stockflow.db")
from fastapi.testclient import TestClient
from app.main import app

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
    category = client.post("/api/categories", json={"name": "Test Category"}, headers=headers)
    assert category.status_code in (200, 409)
    transfer = client.post("/api/transfers", json={"product_id": 1, "from_warehouse_id": 1, "to_warehouse_id": 2, "quantity": 1}, headers=headers)
    assert transfer.status_code == 200
    alerts = client.post("/api/alerts/generate")
    assert alerts.status_code == 200
    assert "created" in alerts.json()

def test_purchase_order_line_and_receiving_flow():
    login = client.post("/api/auth/login", json={"email": "test-admin@example.com", "password": "correct horse"})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    po = client.post("/api/purchase-orders", json={"supplier_id": 1, "warehouse_id": 1, "total": 1}, headers=headers)
    assert po.status_code == 200
    line = client.post(f"/api/purchase-orders/{po.json()['id']}/items", json={"product_id": 1, "quantity": 2, "unit_cost": 10}, headers=headers)
    assert line.status_code == 200
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
    received = client.post(f"/api/purchase-orders/{po.json()['id']}/receive", json={"item_id": line.json()["id"], "quantity": 2}, headers=headers)
    assert received.status_code == 200
    assert received.json()["status"] == "RECEIVED"

