# backend/app/routers/role_requests.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.role_request import RoleRequest
from app.auth import get_current_user, require_admin

router = APIRouter()


class RequestRoleResponse(BaseModel):
    id: str
    user_id: str
    username: str
    display_name: str | None
    status: str
    created_at: str


@router.post("/request")
async def request_role_upgrade(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Labeler requests upgrade to chuyen_gia."""
    if user.role != "labeler":
        raise HTTPException(status_code=400, detail="Chỉ labeler mới có thể xin nâng quyền")

    # Check existing pending request
    existing = await db.execute(
        select(RoleRequest)
        .where(RoleRequest.user_id == user.id)
        .where(RoleRequest.status == "pending")
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Đã có yêu cầu đang chờ duyệt")

    req = RoleRequest(user_id=user.id, requested_role="chuyen_gia")
    db.add(req)
    await db.commit()
    return {"message": "Đã gửi yêu cầu nâng quyền"}


@router.get("", response_model=list[RequestRoleResponse])
async def list_role_requests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: list all pending role requests."""
    result = await db.execute(
        select(RoleRequest, User)
        .join(User, RoleRequest.user_id == User.id)
        .where(RoleRequest.status == "pending")
        .order_by(RoleRequest.created_at)
    )
    rows = result.all()
    return [
        RequestRoleResponse(
            id=req.id,
            user_id=req.user_id,
            username=user.username,
            display_name=user.display_name,
            status=req.status,
            created_at=str(req.created_at),
        )
        for req, user in rows
    ]


@router.patch("/{request_id}/approve")
async def approve_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    req = await db.get(RoleRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Yêu cầu đã được xử lý")

    req.status = "approved"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)

    user = await db.get(User, req.user_id)
    if user:
        user.role = req.requested_role

    await db.commit()
    return {"status": "approved"}


@router.patch("/{request_id}/reject")
async def reject_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    req = await db.get(RoleRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Yêu cầu đã được xử lý")

    req.status = "rejected"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": "rejected"}
