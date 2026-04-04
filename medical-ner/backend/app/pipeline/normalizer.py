import re
from typing import Optional


class SentenceNormalizer:
    """Clean and filter Vietnamese medical sentences"""

    NOISE_PATTERNS = [
        r'Xem thêm:.*',
        r'Nguồn:.*',
        r'Tác giả:.*',
        r'Bình luận.*',
        r'Copyright.*',
        r'\(Ảnh:.*\)',
        r'>>.*',
        r'Đọc thêm:.*'
    ]

    MIN_WORD_COUNT = 3
    MAX_WORD_COUNT = 100
    MIN_CHAR_COUNT = 15
    MIN_ALPHA_RATIO = 0.5

    def normalize(self, text: str) -> Optional[str]:
        """Normalize and filter sentence. Returns None if sentence is low quality."""
        for pattern in self.NOISE_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        text = ' '.join(text.split())

        if not self._is_valid(text):
            return None

        return text

    def _is_valid(self, text: str) -> bool:
        word_count = len(text.split())
        char_count = len(text)

        if word_count < self.MIN_WORD_COUNT or word_count > self.MAX_WORD_COUNT:
            return False

        if char_count < self.MIN_CHAR_COUNT:
            return False

        alpha_count = sum(c.isalpha() for c in text)
        if alpha_count / char_count < self.MIN_ALPHA_RATIO:
            return False

        # Must contain Vietnamese chars or medical terms
        if not re.search(
            r'[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]',
            text.lower()
        ):
            medical_keywords = ['bệnh', 'thuốc', 'triệu chứng', 'điều trị', 'viêm', 'đau']
            if not any(kw in text.lower() for kw in medical_keywords):
                return False

        return True
