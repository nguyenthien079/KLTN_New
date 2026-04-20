from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.auth import get_current_user, hash_password, require_admin

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
    role: str = "chuyen_gia"


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    password: str | None = None


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

    if request.role not in ("admin", "chuyen_gia"):
        raise HTTPException(status_code=400, detail="Role phải là admin hoặc chuyen_gia")

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


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    if request.role is not None and request.role not in ("admin", "chuyen_gia"):
        raise HTTPException(status_code=400, detail="Role phải là admin hoặc chuyen_gia")

    if request.role is not None:
        # Prevent removing own admin role.
        if user.id == current_user.id and request.role != "admin":
            raise HTTPException(status_code=400, detail="Không thể tự hạ quyền admin của chính mình")
        user.role = request.role

    if request.display_name is not None:
        user.display_name = request.display_name

    if request.password:
        user.hashed_password = hash_password(request.password)

    await db.commit()
    await db.refresh(user)
    return UserResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền này")

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Không thể xóa tài khoản của chính mình")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    await db.delete(user)
    await db.commit()
    return {"status": "deleted", "user_id": user_id}
