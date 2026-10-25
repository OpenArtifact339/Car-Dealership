"""Create or promote one admin account explicitly from the command line."""

import getpass
import os

from app.db import connect, initialize
from app.security import hash_password


def main():
    path = os.getenv("DATABASE_PATH", "dealership.db")
    initialize(path)
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password (at least 8 characters): ")
    if "@" not in email or len(password) < 8:
        raise SystemExit("Enter a valid email and a password of at least 8 characters")
    with connect(path) as connection:
        connection.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'admin') "
            "ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash, role='admin'",
            (email, hash_password(password)),
        )
    print("Admin account ready.")


if __name__ == "__main__":
    main()
