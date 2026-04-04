import re
from pathlib import Path
from typing import List, Dict

from .base import BaseExtractor, Entity


class DictionaryExtractor(BaseExtractor):
    """Dictionary-based exact entity matching"""

    def _initialize(self):
        dict_dir = Path("data/dicts")
        self.dictionaries: Dict[str, List[str]] = {}

        dict_files = {
            "DISEASE": "diseases.txt",
            "DRUG": "drugs.txt",
            "SYMPTOM": "symptoms.txt",
            "TREATMENT": "treatments.txt",
            "BODY_PART": "body_parts.txt",
            "TEST": "tests.txt"
        }

        for entity_type, filename in dict_files.items():
            filepath = dict_dir / filename
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    terms = [
                        line.strip().lower()
                        for line in f
                        if line.strip() and not line.startswith('#')
                    ]
                self.dictionaries[entity_type] = terms

        if self.dictionaries:
            self._is_available = True
            total_terms = sum(len(t) for t in self.dictionaries.values())
            print(f"[Dictionary] Loaded {total_terms} terms across {len(self.dictionaries)} categories")

    def extract(self, text: str) -> List[Entity]:
        if not self._is_available:
            return []

        entities = []
        text_lower = text.lower()

        for entity_type, terms in self.dictionaries.items():
            for term in sorted(terms, key=len, reverse=True):  # Longest match first
                pattern = r'\b' + re.escape(term) + r'\b'
                for match in re.finditer(pattern, text_lower):
                    entity = Entity(
                        text=text[match.start():match.end()],
                        normalized_text=term,
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=1.0,
                        source='dictionary'
                    )
                    entities.append(entity)

        return entities
