import re
import unicodedata
from typing import List

from .dictionary import dictionary_match
from .rules import rule_match
from .merger import merge_spans


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def run(text: str) -> List[dict]:
    text_norm = normalize(text)
    dict_spans = dictionary_match(text_norm)
    rule_spans = rule_match(text_norm)
    final = merge_spans(dict_spans, rule_spans)
    return final
