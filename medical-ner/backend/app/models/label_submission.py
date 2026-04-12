from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class LabelSubmission(Base):
    """One labeler's annotation session for one article."""
    __tablename__ = "label_submissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    labeler_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="draft")  # draft | submitted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    annotations = relationship("LabelAnnotation", back_populates="submission",
                                cascade="all, delete-orphan")
