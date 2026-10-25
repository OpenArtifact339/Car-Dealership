"""REST API for accounts, vehicle catalog, and inventory transactions."""

import os
import sqlite3
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from .db import connect, initialize
from .security import create_token, hash_password, token_user_id, verify_password


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # Keep the project dependency-light while still checking basic email shape.
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1] or " " in value:
            raise ValueError("Enter a valid email address")
        return value


class VehicleInput(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    quantity: int = Field(ge=0)

    @field_validator("make", "model", "category")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cannot be blank")
        return value


class VehicleOut(BaseModel):
    id: int
    make: str
    model: str
    category: str
    price: float
    quantity: int


class StockInput(BaseModel):
    amount: int = Field(default=1, gt=0, le=10000)


def vehicle_out(row: sqlite3.Row) -> dict:
    """Keep money as integer cents in storage and expose a familiar API price."""
    return {"id": row["id"], "make": row["make"], "model": row["model"],
            "category": row["category"], "price": row["price_cents"] / 100,
            "quantity": row["quantity"]}


def create_app(database_path: str | None = None, jwt_secret: str | None = None) -> FastAPI:
    """App factory lets tests use their own isolated on-disk database."""
    database_path = database_path or os.getenv("DATABASE_PATH", "dealership.db")
    jwt_secret = jwt_secret or os.getenv("JWT_SECRET", "")
    if not jwt_secret or jwt_secret == "change-me":
        raise RuntimeError("Set JWT_SECRET to a long, random value")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialize(database_path)
        yield

    app = FastAPI(title="Car Dealership Inventory API", lifespan=lifespan)
    # The Vite development server runs on another local origin.
    origins = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
    bearer = HTTPBearer(auto_error=False)

    def db():
        connection = connect(database_path)
        try:
            yield connection
        finally:
            connection.close()

    Db = Annotated[sqlite3.Connection, Depends(db)]

    def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], connection: Db):
        user_id = token_user_id(credentials.credentials, jwt_secret) if credentials else None
        user = connection.execute("SELECT id, email, role FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
        return user

    User = Annotated[sqlite3.Row, Depends(current_user)]

    def admin(user: User):
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user

    Admin = Annotated[sqlite3.Row, Depends(admin)]

    def get_vehicle(connection: sqlite3.Connection, vehicle_id: int):
        row = connection.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return row

    @app.post("/api/auth/register", status_code=201)
    def register(data: Credentials, connection: Db):
        # Public signups are always ordinary users; only the CLI can seed an admin.
        try:
            with connection:
                cursor = connection.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)",
                                            (data.email, hash_password(data.password)))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Email already registered")
        return {"id": cursor.lastrowid, "email": data.email, "role": "user"}

    @app.post("/api/auth/login")
    def login(data: Credentials, connection: Db):
        user = connection.execute("SELECT * FROM users WHERE email = ?", (data.email,)).fetchone()
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return {"access_token": create_token(user["id"], jwt_secret), "token_type": "bearer",
                "user": {"id": user["id"], "email": user["email"], "role": user["role"]}}

    @app.get("/api/vehicles", response_model=list[VehicleOut])
    def list_vehicles(connection: Db, _user: User):
        return [vehicle_out(row) for row in connection.execute("SELECT * FROM vehicles ORDER BY id DESC")]

    @app.get("/api/vehicles/search", response_model=list[VehicleOut])
    def search_vehicles(connection: Db, _user: User, make: str | None = None, model: str | None = None,
                        category: str | None = None, min_price: float | None = Query(default=None, ge=0),
                        max_price: float | None = Query(default=None, ge=0)):
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(status_code=422, detail="Minimum price cannot exceed maximum price")
        clauses, values = [], []
        for name, value in (("make", make), ("model", model), ("category", category)):
            if value:
                # Parameters prevent SQL injection; LIKE gives a friendly partial match.
                clauses.append(f"LOWER({name}) LIKE ?")
                values.append(f"%{value.lower()}%")
        if min_price is not None:
            clauses.append("price_cents >= ?")
            values.append(round(min_price * 100))
        if max_price is not None:
            clauses.append("price_cents <= ?")
            values.append(round(max_price * 100))
        sql = "SELECT * FROM vehicles" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY id DESC"
        return [vehicle_out(row) for row in connection.execute(sql, values)]

    @app.post("/api/vehicles", response_model=VehicleOut, status_code=201)
    def add_vehicle(data: VehicleInput, connection: Db, _admin: Admin):
        with connection:
            cursor = connection.execute("INSERT INTO vehicles (make, model, category, price_cents, quantity) VALUES (?, ?, ?, ?, ?)",
                                        (data.make, data.model, data.category, int(data.price * 100), data.quantity))
        return vehicle_out(get_vehicle(connection, cursor.lastrowid))

    @app.put("/api/vehicles/{vehicle_id}", response_model=VehicleOut)
    def update_vehicle(vehicle_id: int, data: VehicleInput, connection: Db, _admin: Admin):
        get_vehicle(connection, vehicle_id)
        with connection:
            connection.execute("UPDATE vehicles SET make=?, model=?, category=?, price_cents=?, quantity=? WHERE id=?",
                               (data.make, data.model, data.category, int(data.price * 100), data.quantity, vehicle_id))
        return vehicle_out(get_vehicle(connection, vehicle_id))

    @app.delete("/api/vehicles/{vehicle_id}", status_code=204)
    def delete_vehicle(vehicle_id: int, connection: Db, _admin: Admin):
        get_vehicle(connection, vehicle_id)
        with connection:
            connection.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))

    @app.post("/api/vehicles/{vehicle_id}/purchase", response_model=VehicleOut)
    def purchase(vehicle_id: int, connection: Db, _user: User):
        # Conditional UPDATE prevents stock dropping below zero even with concurrent buyers.
        with connection:
            cursor = connection.execute("UPDATE vehicles SET quantity = quantity - 1 WHERE id = ? AND quantity > 0", (vehicle_id,))
        if cursor.rowcount == 0:
            get_vehicle(connection, vehicle_id)
            raise HTTPException(status_code=409, detail="Vehicle is out of stock")
        return vehicle_out(get_vehicle(connection, vehicle_id))

    @app.post("/api/vehicles/{vehicle_id}/restock", response_model=VehicleOut)
    def restock(vehicle_id: int, data: StockInput, connection: Db, _admin: Admin):
        with connection:
            cursor = connection.execute("UPDATE vehicles SET quantity = quantity + ? WHERE id = ?", (data.amount, vehicle_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return vehicle_out(get_vehicle(connection, vehicle_id))

    @app.get("/api/auth/me")
    def me(user: User):
        return {"id": user["id"], "email": user["email"], "role": user["role"]}

    return app


# Uvicorn imports this object; the secret must already be present in the shell.
app = create_app()
