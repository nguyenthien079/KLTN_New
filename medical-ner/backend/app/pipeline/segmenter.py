from underthesea import sent_tokenize
from typing import List


class SentenceSegmenter:
    """Vietnamese sentence segmentation"""

    # Vietnamese abbreviations (không tách)
    ABBREVIATIONS = {
        'BS.', 'TS.', 'PGS.', 'ThS.', 'CN.',  # Titles
        'TP.', 'Q.', 'P.',                      # Locations
        'BVĐK', 'BV', 'TTYT'                   # Medical
    }

    def segment(self, text: str) -> List[str]:
        """Segment text into sentences"""
        protected_text = self._protect_abbreviations(text)
        sentences = sent_tokenize(protected_text)
        sentences = [self._restore_abbreviations(s) for s in sentences]
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _protect_abbreviations(self, text: str) -> str:
        for abbr in self.ABBREVIATIONS:
            text = text.replace(abbr, abbr.replace('.', '<DOT>'))
        return text

    def _restore_abbreviations(self, text: str) -> str:
        return text.replace('<DOT>', '.')
