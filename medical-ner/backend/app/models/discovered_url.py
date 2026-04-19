from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class DiscoveredDomain(Base):
    __tablename__ = "discovered_domains"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    urls = relationship("DiscoveredUrl", back_populates="domain_rel", cascade="all, delete-orphan")


class DiscoveredUrl(Base):
    __tablename__ = "discovered_urls"

    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(Integer, ForeignKey("discovered_domains.id"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    domain_rel = relationship("DiscoveredDomain", back_populates="urls")

    __table_args__ = (
        UniqueConstraint("domain_id", "url", name="uq_discovered_urls_domain_url"),
    )
