from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Tuple
import hashlib


class Deduplicator:
    """Detect duplicate articles using TF-IDF cosine similarity"""

    def __init__(self, threshold: float = 0.90):
        self.threshold = threshold
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 2),
            min_df=1
        )

    def compute_hash(self, text: str) -> str:
        """Compute SHA256 hash of text"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def find_duplicates(
        self,
        texts: List[str],
        existing_texts: List[str] = None
    ) -> List[Tuple[int, int, float]]:
        """
        Find duplicate texts using TF-IDF cosine similarity.

        Returns:
            List of (idx1, idx2, similarity_score)
        """
        all_texts = texts if existing_texts is None else existing_texts + texts

        if len(all_texts) < 2:
            return []

        tfidf_matrix = self.vectorizer.fit_transform(all_texts)
        similarities = cosine_similarity(tfidf_matrix)

        duplicates = []
        n_existing = len(existing_texts) if existing_texts else 0

        for i in range(n_existing, len(all_texts)):
            for j in range(i):
                if similarities[i, j] >= self.threshold:
                    duplicates.append((i, j, float(similarities[i, j])))

        return duplicates
