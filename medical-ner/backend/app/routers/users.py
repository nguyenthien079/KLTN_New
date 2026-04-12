from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.auth import hash_password, require_admin

router = APIRouter()


class UserResponse(BaseModel):
    user_id: str
    username: str
    display_name: str | None
    role: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    role: str = "labeler"


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [
        UserResponse(
            user_id=u.id,
            username=u.username,
            display_name=u.display_name,
            role=u.role,
        )
        for u in users
    ]


@router.post("", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.username == request.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại")

    if request.role not in ("admin", "labeler", "chuyen_gia"):
        raise HTTPException(status_code=400, detail="Role phải là admin, chuyen_gia hoặc labeler")

    user = User(
        username=request.username,
        hashed_password=hash_password(request.password),
        display_name=request.display_name,
        role=request.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )
