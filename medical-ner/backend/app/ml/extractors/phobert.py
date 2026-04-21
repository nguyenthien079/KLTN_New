from pathlib import Path
from typing import List

from .base import BaseExtractor, Entity


class PhoBERTExtractor(BaseExtractor):
    """PhoBERT-based NER extractor using fine-tuned model"""

    def _initialize(self):
        model_path = Path("models/phobert-medical/final_model")

        if not model_path.exists():
            print(f"[PhoBERT] Model not found at {model_path}")
            return

        try:
            from transformers import pipeline, AutoModelForTokenClassification, AutoTokenizer

            model = AutoModelForTokenClassification.from_pretrained(str(model_path))
            tokenizer = AutoTokenizer.from_pretrained(str(model_path))

            self._pipeline = pipeline(
                "token-classification",
                model=model,
                tokenizer=tokenizer,
                aggregation_strategy="simple",
                device=-1
            )

            self._is_available = True
            print(f"[PhoBERT] Loaded from {model_path}")
        except Exception as e:
            print(f"[PhoBERT] Failed to load: {e}")

    def extract(self, text: str) -> List[Entity]:
        if not self._is_available:
            return []

        try:
            results = self._pipeline(text)
            entities = []
            for result in results:
                start = result.get('start')
                end = result.get('end')

                if start is not None and end is not None:
                    word = text[start:end]
                else:
                    raw = result['word']
                    has_bpe_cut = raw.endswith('@@')
                    word = raw.replace('@@', '').strip()
                    if not word:
                        continue
                    start = text.lower().find(word.lower())
                    if start == -1:
                        continue
                    end = start + len(word)
                    # BPE cut: extend end to next whitespace to recover missing chars
                    if has_bpe_cut:
                        while end < len(text) and text[end] not in (' ', '\n', '\t'):
                            end += 1
                    word = text[start:end]

                entity = Entity(
                    text=word,
                    normalized_text=self.normalize_text(word),
                    entity_type=result['entity_group'],
                    start=start,
                    end=end,
                    confidence=float(result['score']),
                    source='phobert'
                )
                entities.append(entity)
            return entities
        except Exception as e:
            print(f"[PhoBERT] Error during extraction: {e}")
            return []
