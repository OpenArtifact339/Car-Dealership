"""Behavior tests for authentication, authorization, search, and stock changes."""

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

# main.py creates the production app at import, so provide a test-only secret first.
os.environ.setdefault("JWT_SECRET", "test-secret-only-do-not-use-in-production-12345")

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from app.main import create_app
from app.security import hash_password


@pytest.fixture
def client(tmp_path):
    # Each test has a fresh real SQLite file, never shared in-memory state.
    app = create_app(str(tmp_path / "test.db"), "isolated-test-secret-1234567890-long-enough")
    with TestClient(app) as test_client:
        yield test_client, str(tmp_path / "test.db")


def token(client, email="user@example.com", password="password123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def admin_token(client, path):
    with connect(path) as connection:
        connection.execute("INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                           ("admin@example.com", hash_password("adminpass123"), "admin"))
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "adminpass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


CAR = {"make": "Honda", "model": "Civic", "category": "Sedan", "price": "19999.99", "quantity": 2}


def add_car(client, headers, **changes):
    return client.post("/api/vehicles", json={**CAR, **changes}, headers=headers)


def test_register_login_duplicate_and_bad_credentials(client):
    api, _ = client
    created = api.post("/api/auth/register", json={"email": " USER@example.com ", "password": "password123"})
    assert created.status_code == 201
    assert created.json()["role"] == "user"  # Registration cannot grant admin.
    assert created.json()["email"] == "user@example.com"
    assert api.post("/api/auth/register", json={"email": "user@example.com", "password": "password123"}).status_code == 409
    assert api.post("/api/auth/login", json={"email": "user@example.com", "password": "wrongpass"}).status_code == 401
    login = api.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}).json()["role"] == "user"


def test_protected_routes_and_admin_permissions(client):
    api, path = client
    regular = token(api)
    admin = admin_token(api, path)
    assert api.get("/api/vehicles").status_code == 401
    assert api.get("/api/vehicles", headers={"Authorization": "Bearer broken"}).status_code == 401
    assert add_car(api, regular).status_code == 403
    created = add_car(api, admin)
    assert created.status_code == 201
    vehicle_id = created.json()["id"]
    assert api.put(f"/api/vehicles/{vehicle_id}", json=CAR, headers=regular).status_code == 403
    assert api.delete(f"/api/vehicles/{vehicle_id}", headers=regular).status_code == 403
    assert api.post(f"/api/vehicles/{vehicle_id}/restock", json={"amount": 2}, headers=regular).status_code == 403
    assert api.get("/api/vehicles", headers=regular).json()[0]["id"] == vehicle_id


def test_search_filters_update_and_delete(client):
    api, path = client
    admin = admin_token(api, path)
    first = add_car(api, admin).json()["id"]
    add_car(api, admin, make="Toyota", model="Corolla", category="Hatchback", price="15000.00")
    result = api.get("/api/vehicles/search", params={"make": "hon", "category": "sed", "min_price": 19000,
                                                       "max_price": 20000}, headers=admin)
    assert [car["id"] for car in result.json()] == [first]
    assert api.get("/api/vehicles/search", params={"min_price": 5, "max_price": 1}, headers=admin).status_code == 422
    changed = api.put(f"/api/vehicles/{first}", json={**CAR, "price": "18999.50", "quantity": 0}, headers=admin)
    assert changed.json()["price"] == 18999.5
    assert changed.json()["quantity"] == 0
    assert api.delete(f"/api/vehicles/{first}", headers=admin).status_code == 204
    assert api.delete(f"/api/vehicles/{first}", headers=admin).status_code == 404


def test_purchase_restock_and_not_found(client):
    api, path = client
    regular = token(api)
    admin = admin_token(api, path)
    vehicle_id = add_car(api, admin, quantity=1).json()["id"]
    route = f"/api/vehicles/{vehicle_id}"
    assert api.post(route + "/purchase", headers=regular).json()["quantity"] == 0
    assert api.post(route + "/purchase", headers=regular).status_code == 409
    assert api.post(route + "/restock", json={"amount": 0}, headers=admin).status_code == 422
    assert api.post(route + "/restock", json={"amount": 3}, headers=admin).json()["quantity"] == 3
    assert api.post("/api/vehicles/999/purchase", headers=regular).status_code == 404
    assert api.post("/api/vehicles/999/restock", json={"amount": 1}, headers=admin).status_code == 404


def test_validation_and_persistence(client):
    api, path = client
    admin = admin_token(api, path)
    assert add_car(api, admin, price="0").status_code == 422
    assert add_car(api, admin, quantity=-1).status_code == 422
    assert add_car(api, admin, make=" ").status_code == 422
    vehicle_id = add_car(api, admin).json()["id"]
    # Read the actual file to establish this is persistent storage.
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT quantity FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()[0] == 2


def test_two_buyers_cannot_both_purchase_the_last_car(client):
    api, path = client
    regular = token(api)
    admin = admin_token(api, path)
    vehicle_id = add_car(api, admin, quantity=1).json()["id"]

    # Both requests race against the same SQLite row; only one may succeed.
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: api.post(f"/api/vehicles/{vehicle_id}/purchase", headers=regular), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    with connect(path) as connection:
        assert connection.execute("SELECT quantity FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()[0] == 0
