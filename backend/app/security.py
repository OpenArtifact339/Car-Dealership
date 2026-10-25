"""Password storage and short-lived bearer tokens."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Store a random salt and a PBKDF2 digest, never the original password."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Use constant-time comparison to check a login attempt."""
    try:
        scheme, count, salt, expected = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(count))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, secret: str) -> str:
    """Sign a token containing the user's ID and an expiration timestamp."""
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=8)}, secret, algorithm="HS256")


def token_user_id(token: str, secret: str) -> int | None:
    """Reject expired, modified, and malformed tokens."""
    try:
        value = jwt.decode(token, secret, algorithms=["HS256"])
        user_id = int(value["sub"])
        return user_id if user_id > 0 else None
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        return None
