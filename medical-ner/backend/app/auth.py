import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
VALID_ROLES = {"admin", "chuyen_gia", "reviewer"}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def parse_roles(raw: str | None) -> list[str]:
    values = [x.strip() for x in (raw or "").split(",") if x.strip()]
    roles = [x for x in values if x in VALID_ROLES]
    if not roles:
        return ["chuyen_gia"]
    return list(dict.fromkeys(roles))


def normalize_roles(roles: list[str] | None) -> list[str]:
    if not roles:
        return ["chuyen_gia"]
    normalized = [r.strip() for r in roles if r and r.strip()]
    invalid = [r for r in normalized if r not in VALID_ROLES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Role không hợp lệ: {invalid}")
    deduped = list(dict.fromkeys(normalized))
    return deduped or ["chuyen_gia"]


def roles_to_csv(roles: list[str]) -> str:
    return ",".join(normalize_roles(roles))


def has_role(user: User, role: str) -> bool:
    return role in parse_roles(user.role)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token không hợp lệ")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Người dùng không tồn tại")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản đã bị vô hiệu hóa")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not has_role(user, "admin"):
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền này")
    return user


