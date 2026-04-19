import json
import re
from pathlib import Path
from typing import List

_DICT_PATH = Path(__file__).parent.parent.parent / "data" / "dicts" / "medical_terms.json"

# {search_term_lowercase: label}
_lookup: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _lookup
    if _lookup is not None:
        return _lookup

    if not _DICT_PATH.exists():
        _lookup = {}
        return _lookup

    with open(_DICT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    terms: dict[str, str] = {k.lower(): v for k, v in data.get("terms", {}).items()}
    aliases: dict[str, str] = {k.lower(): v.lower() for k, v in data.get("aliases", {}).items()}

    _lookup = dict(terms)
    for alias, canonical in aliases.items():
        if canonical in terms:
            _lookup[alias] = terms[canonical]

    return _lookup


def dictionary_match(text: str) -> List[dict]:
    lookup = _load()
    text_lower = text.lower()
    spans: List[dict] = []

    for term in sorted(lookup, key=len, reverse=True):
        label = lookup[term]
        pattern = r'\b' + re.escape(term) + r'\b'
        for m in re.finditer(pattern, text_lower):
            spans.append({
                "text": text[m.start():m.end()],
                "label": label,
                "start": m.start(),
                "end": m.end(),
                "source": "dict",
            })

    return spans
