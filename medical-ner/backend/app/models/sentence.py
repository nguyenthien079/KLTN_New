from sqlalchemy import Column, Integer, Text, DateTime, Boolean, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class PipelineStatus(str, enum.Enum):
    RAW = "raw"
    SEGMENTED = "segmented"
    NORMALIZED = "normalized"
    DEDUPLICATED = "deduplicated"
    PROCESSED = "processed"


class Sentence(Base):
    __tablename__ = "sentences"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), index=True)

    # Content
    raw_text = Column(Text, nullable=False)
    normalized_text = Column(Text)
    char_count = Column(Integer)
    word_count = Column(Integer)

    # Processing status
    pipeline_status = Column(
        SQLEnum(PipelineStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=PipelineStatus.RAW,
        index=True,
    )

    # Quality flags
    is_medical = Column(Boolean, default=False, index=True)
    medical_confidence = Column(Float)
    is_duplicate = Column(Boolean, default=False, index=True)
    duplicate_of_id = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))

    # Relationships
    article = relationship("Article", back_populates="sentences")
    entities = relationship("KnowledgeMap", back_populates="sentence")
