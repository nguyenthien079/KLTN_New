from typing import List, Dict


def compute_entity_stats(entities: List[Dict]) -> Dict:
    """Compute statistics for a list of extracted entities"""
    if not entities:
        return {"total": 0, "by_type": {}, "avg_confidence": 0.0}

    by_type: Dict[str, int] = {}
    total_confidence = 0.0

    for entity in entities:
        etype = entity.get("entity_type") or entity.get("type", "UNKNOWN")
        by_type[etype] = by_type.get(etype, 0) + 1
        total_confidence += entity.get("confidence", 0.0)

    return {
        "total": len(entities),
        "by_type": by_type,
        "avg_confidence": round(total_confidence / len(entities), 4)
    }
