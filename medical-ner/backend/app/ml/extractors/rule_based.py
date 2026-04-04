import re
from typing import List, Dict

from .base import BaseExtractor, Entity


class RuleBasedExtractor(BaseExtractor):
    """Regex pattern-based Vietnamese medical entity extraction"""

    def _initialize(self):
        self.patterns: Dict[str, List[str]] = {
            'DISEASE': [
                r'\bviêm\s+\w+',
                r'\bbệnh\s+\w+(?:\s+\w+)?',
                r'\b\w+\s+mãn tính',
                r'\b\w+\s+cấp tính',
                r'\bung thư\s+\w+',
                r'\b\w+\s+ác tính',
            ],
            'SYMPTOM': [
                r'\bsốt\s+(?:cao|nhẹ)?',
                r'\bđau\s+\w+',
                r'\bbuồn nôn',
                r'\bchóng mặt',
                r'\bmệt mỏi',
                r'\bho\s+(?:khan|có đờm)?',
            ],
            'TREATMENT': [
                r'\bphẫu thuật\s+\w*',
                r'\bhóa\s+trị(?:liệu)?',
                r'\bxạ\s+trị(?:liệu)?',
                r'\bvật lý\s+trị liệu',
                r'\bđiều trị\s+\w+',
            ],
            'DRUG': [
                r'\bthuốc\s+\w+',
                r'\b\w+cillin\b',
                r'\bvitamin\s+[A-Za-z]\d?',
            ]
        }

        self._is_available = True
        total = sum(len(p) for p in self.patterns.values())
        print(f"[Rule-Based] Loaded {total} patterns")

    def extract(self, text: str) -> List[Entity]:
        if not self._is_available:
            return []

        entities = []
        for entity_type, patterns in self.patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    matched = match.group().strip()
                    if not matched:
                        continue
                    entity = Entity(
                        text=matched,
                        normalized_text=self.normalize_text(matched),
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.7,
                        source='rule_based'
                    )
                    entities.append(entity)

        return entities
