from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.auth import hash_password, verify_password, create_access_token, get_current_user, parse_roles

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    display_name: str | None
    role: str
    roles: list[str]


class MeResponse(BaseModel):
    user_id: str
    username: str
    display_name: str | None
    role: str
    roles: list[str]


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    if user and not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản đã bị vô hiệu hóa")
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

    roles = parse_roles(user.role)
    token = create_access_token({"sub": user.id, "roles": roles})
    return LoginResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=roles[0],
        roles=roles,
    )


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    roles = parse_roles(user.role)
    return MeResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=roles[0],
        roles=roles,
    )
