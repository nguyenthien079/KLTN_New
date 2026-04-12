from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class LabelAssignment(Base):
    """Optional: admin/expert assigns an article to a specific labeler."""
    __tablename__ = "label_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    labeler_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assigned_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    blind_mode = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
