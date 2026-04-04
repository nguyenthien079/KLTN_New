"""
NER inference module — thin wrapper around MedicalNERPipeline for convenience.

Usage:
    from app.ml.inference import NERInference
    ner = NERInference()
    results = ner.predict("Bệnh nhân bị viêm phổi nặng")
"""
from typing import List, Dict

from app.ml.ensemble import MedicalNERPipeline


class NERInference:
    """Convenience wrapper for running NER inference"""

    def __init__(self, min_confidence: float = 0.4):
        self.pipeline = MedicalNERPipeline(
            use_phobert=True,
            use_dictionary=True,
            use_rule_based=True,
            min_confidence=min_confidence
        )

    def predict(self, text: str) -> List[Dict]:
        """
        Run NER on text and return list of entity dicts.

        Returns:
            [{"text": ..., "type": ..., "start": ..., "end": ..., "confidence": ..., "source": ...}]
        """
        entities = self.pipeline.extract(text)
        return [
            {
                "text": e.text,
                "type": e.entity_type,
                "start": e.start,
                "end": e.end,
                "confidence": round(e.confidence, 4),
                "source": e.source
            }
            for e in entities
        ]

    def predict_batch(self, texts: List[str]) -> List[List[Dict]]:
        """Run NER on a list of texts"""
        return [self.predict(text) for text in texts]
