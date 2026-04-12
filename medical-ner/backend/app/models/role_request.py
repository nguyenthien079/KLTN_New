from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class RoleRequest(Base):
    __tablename__ = "role_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    requested_role = Column(String(20), nullable=False, default="chuyen_gia")
    status = Column(String(20), nullable=False, default="pending")  # pending/approved/rejected
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
