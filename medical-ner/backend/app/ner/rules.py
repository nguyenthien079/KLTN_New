import re
from typing import List

RULES = {
    "DOSAGE": [
        r'\b\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|µg|ml|l|đơn vị|IU|UI)\b',
        r'\b\d+\s*(?:viên|ống|gói|chai|lọ)(?:\s*/\s*(?:ngày|lần|tuần))?\b',
        r'\b(?:uống|tiêm|dùng)\s+\d+\s*(?:mg|g|ml|viên|lần)\b',
        r'\b\d+\s*lần\s*/\s*ngày\b',
    ],
    "LAB_VALUE": [
        r'\b(?:glucose|đường huyết|cholesterol|triglyceride|creatinine|hemoglobin|bạch cầu|hồng cầu|tiểu cầu|HbA1c)\s*[:=]\s*\d+(?:[.,]\d+)?\s*(?:mmol/L|mg/dL|g/dL|%|U/L|IU/L|G/L)?\b',
        r'\b\d+(?:[.,]\d+)?\s*(?:mmol/L|mg/dL|g/dL|U/L|IU/L)\b',
        r'\bBMI\s*[:=]?\s*\d+(?:[.,]\d+)?\b',
        r'\bhuyết áp\s*[:=]?\s*\d+/\d+\s*(?:mmHg)?\b',
    ],
    "AGE": [
        r'\b\d+\s*tuổi\b',
        r'\btuổi\s*:\s*\d+\b',
        r'\b(?:nam|nữ)\s*,?\s*\d+\s*tuổi\b',
        r'\btrẻ\s+\d+\s*tuổi\b',
    ],
    "DISEASE": [
        r'\bviêm\s+\w+(?:\s+\w+)?\b',
        r'\bbệnh\s+\w+(?:\s+\w+)?\b',
        r'\bung\s+thư\s+\w+(?:\s+\w+)?\b',
        r'\b\w+\s+mãn\s+tính\b',
        r'\b\w+\s+cấp\s+tính\b',
        r'\bsuy\s+\w+\b',
    ],
    "SYMPTOM": [
        r'\bsốt\s*(?:cao|nhẹ|kéo\s+dài)?\b',
        r'\bđau\s+\w+(?:\s+\w+)?\b',
        r'\bbuồn\s+nôn\b',
        r'\bnôn\s+mửa\b',
        r'\bchóng\s+mặt\b',
        r'\bmệt\s+mỏi\b',
        r'\bho\s*(?:khan|có\s+đờm|ra\s+máu)?\b',
        r'\bkhó\s+thở\b',
        r'\bphù\s*\w*\b',
        r'\btê\s+\w+\b',
        r'\bngứa\s*\w*\b',
    ],
    "TREATMENT": [
        r'\bphẫu\s+thuật\s*\w*\b',
        r'\bhóa\s+trị(?:\s+liệu)?\b',
        r'\bxạ\s+trị(?:\s+liệu)?\b',
        r'\bvật\s+lý\s+trị\s+liệu\b',
        r'\bđiều\s+trị\s+\w+(?:\s+\w+)?\b',
        r'\bnhập\s+viện\b',
        r'\bcắt\s+\w+\b',
    ],
    "DRUG": [
        r'\bthuốc\s+\w+(?:\s+\w+)?\b',
        r'\b\w+cillin\b',
        r'\bvitamin\s+[A-Za-z]\d*\b',
        r'\b\w+statin\b',
        r'\b\w+mycin\b',
        r'\b\w+azole\b',
        r'\b\w+pril\b',
        r'\b\w+sartan\b',
    ],
}


def rule_match(text: str) -> List[dict]:
    spans: List[dict] = []
    for label, patterns in RULES.items():
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE | re.UNICODE):
                matched = m.group().strip()
                if not matched:
                    continue
                start = m.start() + (len(m.group()) - len(m.group().lstrip()))
                spans.append({
                    "text": matched,
                    "label": label,
                    "start": start,
                    "end": start + len(matched),
                    "source": "rule",
                })
    return spans
