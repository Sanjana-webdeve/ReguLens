import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

ALGO = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def _encode(payload: dict, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + timedelta(minutes=minutes), "jti": uuid.uuid4().hex}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)


def create_access_token(user_id: int, role: str) -> str:
    return _encode({"sub": str(user_id), "role": role, "typ": "access"}, settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def create_reset_token(user_id: int, pw_hash: str) -> str:
    # `ph` ties the token to the current password hash, so it is single-use
    return _encode({"sub": str(user_id), "typ": "reset", "ph": pw_hash[-12:]}, settings.RESET_TOKEN_EXPIRE_MINUTES)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
