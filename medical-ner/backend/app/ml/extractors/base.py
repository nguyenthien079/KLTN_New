from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class Entity:
    """Extracted entity data class"""
    text: str             # Original text span
    normalized_text: str  # Lowercased/normalized
    entity_type: str      # DISEASE, DRUG, SYMPTOM, TREATMENT, BODY_PART, TEST
    start: int            # Start character position in text
    end: int              # End character position
    confidence: float     # 0.0 - 1.0
    source: str           # Extractor name


class BaseExtractor(ABC):
    """Abstract base class for entity extractors"""

    def __init__(self):
        self.name = self.__class__.__name__
        self._is_available = False
        self._initialize()

    @abstractmethod
    def _initialize(self):
        """Initialize extractor resources (load models, dicts, etc.)"""
        pass

    @abstractmethod
    def extract(self, text: str) -> List[Entity]:
        """Extract entities from text"""
        pass

    def is_available(self) -> bool:
        return self._is_available

    def normalize_text(self, text: str) -> str:
        return text.lower().strip()
