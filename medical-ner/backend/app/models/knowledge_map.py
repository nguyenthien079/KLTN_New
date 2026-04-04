from sqlalchemy import Column, Integer, Float, ForeignKey, String
from sqlalchemy.orm import relationship
from app.database import Base


class KnowledgeMap(Base):
    __tablename__ = "knowledge_map"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    sentence_id = Column(Integer, ForeignKey("sentences.id", ondelete="CASCADE"), index=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), index=True)

    # Entity details
    start_pos = Column(Integer)
    end_pos = Column(Integer)
    confidence = Column(Float)
    extractor_source = Column(String(50))  # 'phobert', 'dictionary', 'rule_based'

    # Relationships
    sentence = relationship("Sentence", back_populates="entities")
    entity = relationship("Entity", back_populates="knowledge_maps")
