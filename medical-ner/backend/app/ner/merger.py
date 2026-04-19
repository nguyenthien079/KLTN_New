from typing import List


def merge_spans(dict_spans: List[dict], rule_spans: List[dict]) -> List[dict]:
    all_spans = dict_spans + rule_spans

    # sort: start ASC, length DESC, then dict before rule on ties
    all_spans.sort(key=lambda s: (
        s["start"],
        -(s["end"] - s["start"]),
        0 if s["source"] == "dict" else 1,
    ))

    result: List[dict] = []
    for span in all_spans:
        if not any(_overlaps(span, accepted) for accepted in result):
            result.append(span)

    return result


def _overlaps(a: dict, b: dict) -> bool:
    return not (a["end"] <= b["start"] or b["end"] <= a["start"])
