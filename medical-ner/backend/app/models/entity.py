from sqlalchemy import Column, Integer, String, Enum as SQLEnum, DateTime, Float, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class EntityType(str, enum.Enum):
    DISEASE = "DISEASE"
    DRUG = "DRUG"
    SYMPTOM = "SYMPTOM"
    TREATMENT = "TREATMENT"
    BODY_PART = "BODY_PART"
    TEST = "TEST"


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)

    # Entity info
    text = Column(String(512), nullable=False, index=True)
    normalized_text = Column(String(512), index=True)
    entity_type = Column(SQLEnum(EntityType, native_enum=False), nullable=False, index=True)

    # Statistics
    frequency = Column(Integer, default=1)
    avg_confidence = Column(Float)

    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    knowledge_maps = relationship("KnowledgeMap", back_populates="entity")

    __table_args__ = (
        UniqueConstraint("text", "entity_type", name="uq_entity_text_type"),
    )
