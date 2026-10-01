from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ADMIN, ALL_ROLES, get_current_user, require_roles
from app.core.security import (create_access_token, create_reset_token, decode_token, hash_password,
                               verify_password)
from app.models import RevokedToken, User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)


class UserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    first = db.scalar(select(func.count(User.id))) == 0
    user = User(email=email, full_name=body.full_name, password_hash=hash_password(body.password),
                role=ADMIN if first else "viewer")
    db.add(user)
    db.commit()
    audit.log(db, "user.register", user, "user", user.id)
    return user_out(user)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        audit.log(db, "user.login", None, "user", body.email, result="failure")
        raise HTTPException(401, "Incorrect email or password.")
    audit.log(db, "user.login", user, "user", user.id)
    return {"access_token": create_access_token(user.id, user.role), "token_type": "bearer", "user": user_out(user)}


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.merge(RevokedToken(jti=user._jti, expires_at=datetime.fromtimestamp(user._exp, timezone.utc).replace(tzinfo=None)))
    db.commit()
    audit.log(db, "user.logout", user, "user", user.id)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    resp = {"message": "If that account exists, a reset link has been issued."}
    if user:
        token = create_reset_token(user.id, user.password_hash)
        audit.log(db, "user.password_reset_requested", user, "user", user.id)
        if settings.DEBUG_RETURN_RESET_TOKEN:  # dev only: wire to an email provider in production
            resp["reset_token"] = token
    return resp


@router.post("/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    try:
        p = decode_token(body.token)
    except jwt.PyJWTError:
        raise HTTPException(400, "This reset link is invalid or has expired.")
    user = db.get(User, int(p["sub"])) if p.get("typ") == "reset" else None
    if not user or user.password_hash[-12:] != p.get("ph"):
        raise HTTPException(400, "This reset link is invalid or has expired.")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    audit.log(db, "user.password_reset", user, "user", user.id)
    return {"ok": True}


@router.get("/users")
def list_users(db: Session = Depends(get_db), _=Depends(require_roles(ADMIN))):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.id)).all()]


@router.patch("/users/{user_id}")
def patch_user(user_id: int, body: UserPatch, db: Session = Depends(get_db), admin: User = Depends(require_roles(ADMIN))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found.")
    if body.role is not None:
        if body.role not in ALL_ROLES:
            raise HTTPException(400, "Unknown role.")
        u.role = body.role
    if body.is_active is not None:
        if u.id == admin.id and not body.is_active:
            raise HTTPException(400, "You cannot deactivate your own account.")
        u.is_active = body.is_active
    db.commit()
    audit.log(db, "user.update", admin, "user", u.id, {"role": u.role, "is_active": u.is_active})
    return user_out(u)
