import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import RevokedToken, User

bearer = HTTPBearer(auto_error=False)

ADMIN, ANALYST, AUDITOR, VIEWER = "admin", "analyst", "auditor", "viewer"
ALL_ROLES = (ADMIN, ANALYST, AUDITOR, VIEWER)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated. Please log in again.")
    if not creds:
        raise err
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise err
    if payload.get("typ") != "access":
        raise err
    if db.get(RevokedToken, payload["jti"]):
        raise err
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise err
    user._jti = payload["jti"]
    user._exp = payload["exp"]
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role does not have access to this action.")
        return user

    return checker
