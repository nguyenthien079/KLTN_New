from typing import List, Dict, Tuple, Optional
import json
import re
import random
from pathlib import Path


class DataPreparator:
    """Prepare BIO-tagged training data from medical dictionaries"""

    def __init__(self, dict_dir: Path):
        self.dictionaries = self._load_dictionaries(dict_dir)
        self.label_map = self._create_label_map()

    def _load_dictionaries(self, dict_dir: Path) -> Dict[str, List[str]]:
        dict_files = {
            "DISEASE": "diseases.txt",
            "DRUG": "drugs.txt",
            "SYMPTOM": "symptoms.txt",
            "TREATMENT": "treatments.txt",
            "BODY_PART": "body_parts.txt",
            "TEST": "tests.txt"
        }

        dicts = {}
        for entity_type, filename in dict_files.items():
            filepath = dict_dir / filename
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    terms = [
                        line.strip().lower()
                        for line in f
                        if line.strip() and not line.startswith('#')
                    ]
                dicts[entity_type] = terms

        return dicts

    def _create_label_map(self) -> Dict[str, int]:
        labels = ['O']
        for entity_type in self.dictionaries.keys():
            labels.append(f'B-{entity_type}')
            labels.append(f'I-{entity_type}')
        return {label: idx for idx, label in enumerate(labels)}

    def label_sentence(self, text: str) -> Tuple[List[str], List[str]]:
        """Label a sentence with BIO tags using dictionary matching"""
        tokens = text.split()
        tags = ['O'] * len(tokens)
        text_lower = text.lower()

        for entity_type, terms in self.dictionaries.items():
            for term in sorted(terms, key=len, reverse=True):  # Longest match first
                pattern = r'\b' + re.escape(term) + r'\b'
                for match in re.finditer(pattern, text_lower):
                    start_char = match.start()
                    end_char = match.end()

                    start_token, end_token = self._char_to_token_indices(
                        text, tokens, start_char, end_char
                    )

                    if start_token is not None and end_token is not None:
                        tags[start_token] = f'B-{entity_type}'
                        for i in range(start_token + 1, end_token + 1):
                            tags[i] = f'I-{entity_type}'

        return tokens, tags

    def _char_to_token_indices(
        self,
        text: str,
        tokens: List[str],
        start_char: int,
        end_char: int
    ) -> Tuple[Optional[int], Optional[int]]:
        """Convert character positions to token indices"""
        current_pos = 0
        start_token = None
        end_token = None

        for i, token in enumerate(tokens):
            token_start = text.find(token, current_pos)
            if token_start == -1:
                continue
            token_end = token_start + len(token)

            if token_start <= start_char < token_end:
                start_token = i
            if token_start < end_char <= token_end:
                end_token = i

            current_pos = token_end

        return start_token, end_token

    def create_dataset(self, sentences: List[str]) -> List[Dict]:
        """Create labeled dataset, skipping sentences with no entities"""
        dataset = []
        for sentence in sentences:
            tokens, tags = self.label_sentence(sentence)
            if all(tag == 'O' for tag in tags):
                continue
            dataset.append({
                "text": sentence,
                "tokens": tokens,
                "tags": tags,
                "tag_ids": [self.label_map[tag] for tag in tags]
            })
        return dataset

    def split_dataset(
        self,
        dataset: List[Dict],
        train_ratio: float = 0.8,
        val_ratio: float = 0.1
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Split dataset into train/val/test"""
        random.shuffle(dataset)
        n = len(dataset)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        return dataset[:train_end], dataset[train_end:val_end], dataset[val_end:]
