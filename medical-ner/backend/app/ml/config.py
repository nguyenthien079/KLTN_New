from typing import Dict, List

# Entity types
ENTITY_TYPES: Dict[str, str] = {
    'DISEASE': 'Bệnh',
    'DRUG': 'Thuốc',
    'SYMPTOM': 'Triệu chứng',
    'TREATMENT': 'Phương pháp điều trị',
    'BODY_PART': 'Cơ quan cơ thể',
    'TEST': 'Xét nghiệm'
}

# BIO labels (13 total)
BIO_LABELS: List[str] = [
    'O',
    'B-DISEASE', 'I-DISEASE',
    'B-DRUG', 'I-DRUG',
    'B-SYMPTOM', 'I-SYMPTOM',
    'B-TREATMENT', 'I-TREATMENT',
    'B-BODY_PART', 'I-BODY_PART',
    'B-TEST', 'I-TEST'
]

# Ensemble extractor weights
ENSEMBLE_WEIGHTS: Dict[str, float] = {
    'phobert': 1.5,      # Transformer (highest accuracy)
    'dictionary': 1.0,   # Exact matching (high precision)
    'rule_based': 0.7,   # Regex patterns (good recall)
    'vncorenlp': 0.6     # Optional Vietnamese NLP
}

MIN_CONFIDENCE: float = 0.5

PHOBERT_CONFIG = {
    'model_name': 'vinai/phobert-base',
    'max_length': 256,
    'num_labels': len(BIO_LABELS),
    'learning_rate': 2e-5,
    'num_epochs': 5,
    'batch_size': 16,
    'freeze_layers': 8
}
