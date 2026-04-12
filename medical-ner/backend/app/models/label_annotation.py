from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class LabelAnnotation(Base):
    """Single entity annotation within a submission."""
    __tablename__ = "label_annotations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id = Column(String(36), ForeignKey("label_submissions.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    surface_text = Column(String(500), nullable=True)  # denormalized for display
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    submission = relationship("LabelSubmission", back_populates="annotations")
