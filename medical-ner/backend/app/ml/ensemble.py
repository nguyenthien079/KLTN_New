from typing import List, Dict
from .extractors.base import Entity
from .extractors.phobert import PhoBERTExtractor
from .extractors.dictionary import DictionaryExtractor
from .extractors.rule_based import RuleBasedExtractor
from .config import ENSEMBLE_WEIGHTS, MIN_CONFIDENCE


class MedicalNERPipeline:
    """Ensemble NER pipeline with weighted confidence voting"""

    def __init__(
        self,
        use_phobert: bool = True,
        use_dictionary: bool = True,
        use_rule_based: bool = True,
        min_confidence: float = MIN_CONFIDENCE
    ):
        self.min_confidence = min_confidence
        self.weights = ENSEMBLE_WEIGHTS
        self.extractors = []

        if use_phobert:
            try:
                ext = PhoBERTExtractor()
                if ext.is_available():
                    self.extractors.append(ext)
            except Exception as e:
                print(f"PhoBERT init failed: {e}")

        if use_dictionary:
            try:
                ext = DictionaryExtractor()
                if ext.is_available():
                    self.extractors.append(ext)
            except Exception as e:
                print(f"Dictionary init failed: {e}")

        if use_rule_based:
            try:
                ext = RuleBasedExtractor()
                if ext.is_available():
                    self.extractors.append(ext)
            except Exception as e:
                print(f"Rule-based init failed: {e}")

        if not self.extractors:
            raise RuntimeError("No extractors available!")

        print(f"[Ensemble] Ready with {len(self.extractors)} extractors")

    def extract(self, text: str) -> List[Entity]:
        """Extract entities using all extractors and apply weighted voting"""
        if not text or not text.strip():
            return []

        all_entities: List[Entity] = []
        for extractor in self.extractors:
            try:
                all_entities.extend(extractor.extract(text))
            except Exception as e:
                print(f"Extractor {extractor.name} failed: {e}")

        if not all_entities:
            return []

        grouped = self._group_entities(all_entities)

        final_entities = []
        for group in grouped:
            weighted_conf = sum(
                e.confidence * self.weights.get(e.source, 0.5) for e in group
            )
            total_weight = sum(self.weights.get(e.source, 0.5) for e in group)
            final_conf = weighted_conf / total_weight if total_weight > 0 else 0.5

            if final_conf < self.min_confidence:
                continue

            rep = group[0]
            final_entities.append(Entity(
                text=rep.text,
                normalized_text=rep.normalized_text,
                entity_type=rep.entity_type,
                start=rep.start,
                end=rep.end,
                confidence=final_conf,
                source='+'.join(sorted(set(e.source for e in group)))
            ))

        return final_entities

    def _group_entities(self, entities: List[Entity]) -> List[List[Entity]]:
        """Group overlapping entities of the same type"""
        groups = []
        used = set()

        for i, entity in enumerate(entities):
            if i in used:
                continue
            group = [entity]
            used.add(i)
            for j, other in enumerate(entities[i + 1:], start=i + 1):
                if j in used:
                    continue
                if entity.entity_type == other.entity_type and self._is_overlapping(entity, other):
                    group.append(other)
                    used.add(j)
            groups.append(group)

        return groups

    def _is_overlapping(self, e1: Entity, e2: Entity) -> bool:
        if None in (e1.start, e1.end, e2.start, e2.end):
            return e1.normalized_text == e2.normalized_text
        return not (e1.end <= e2.start or e2.end <= e1.start)

    def get_info(self) -> Dict:
        return {
            "extractors": [ext.name for ext in self.extractors],
            "weights": self.weights,
            "min_confidence": self.min_confidence
        }
