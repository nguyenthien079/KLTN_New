from transformers import AutoModel, AutoTokenizer
import torch
import numpy as np
from typing import List
from sklearn.metrics.pairwise import cosine_similarity


class SemanticDeduplicator:
    """Remove duplicate sentences using PhoBERT embeddings"""

    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold
        self.model_name = "vinai/phobert-base"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.eval()

    def encode(self, sentences: List[str]) -> np.ndarray:
        """Encode sentences to mean-pooled PhoBERT embeddings"""
        embeddings = []
        with torch.no_grad():
            for sentence in sentences:
                inputs = self.tokenizer(
                    sentence,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=256
                )
                outputs = self.model(**inputs)
                embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
                embeddings.append(embedding)
        return np.array(embeddings)

    def find_duplicates(self, sentences: List[str]) -> List[int]:
        """
        Find duplicate sentences.

        Returns:
            List of indices to REMOVE (keeping first occurrence of each duplicate group)
        """
        if len(sentences) < 2:
            return []

        embeddings = self.encode(sentences)
        sim_matrix = cosine_similarity(embeddings)

        to_remove = set()
        for i in range(len(sentences)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(sentences)):
                if sim_matrix[i, j] >= self.threshold:
                    to_remove.add(j)

        return list(to_remove)
