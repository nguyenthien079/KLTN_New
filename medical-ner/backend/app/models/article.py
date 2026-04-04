from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class CrawlStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), unique=True, nullable=False, index=True)
    title = Column(String(512))
    source_domain = Column(String(255), index=True)

    # Content
    raw_html = Column(Text)
    clean_text = Column(Text)
    char_count = Column(Integer)

    # Metadata
    crawl_batch_id = Column(Integer, index=True)
    crawled_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(SQLEnum(CrawlStatus), default=CrawlStatus.PENDING, index=True)

    # Deduplication
    content_hash = Column(String(64), index=True)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(Integer, nullable=True)
    similarity_score = Column(Float, nullable=True)

    # Relationships
    sentences = relationship("Sentence", back_populates="article", cascade="all, delete-orphan")
