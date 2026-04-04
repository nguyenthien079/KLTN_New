from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSON
from app.database import Base
import uuid


class Correction(Base):
    """
    Model to store human corrections for NER predictions.
    Used for human-in-the-loop annotation and training data export.
    """
    __tablename__ = "corrections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_text = Column(Text, nullable=False)  # Original sentence
    original_entities = Column(JSON, nullable=False)  # Model predictions
    corrected_entities = Column(JSON, nullable=False)  # Human-corrected entities
    created_at = Column(DateTime(timezone=True), server_default=func.now())
