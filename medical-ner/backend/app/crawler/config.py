from pydantic import BaseModel
from typing import List


class CrawlerConfig(BaseModel):
    # Medical keywords for URL filtering
    medical_keywords: List[str] = [
        "thuoc", "benh", "trieu-chung", "dieu-tri",
        "hoat-chat", "duoc", "y-te", "suc-khoe",
        "cham-soc", "phong-ngua"
    ]

    # Crawl limits
    max_pages_per_site: int = 100
    max_depth: int = 2

    # Duplicate detection
    similarity_threshold: float = 0.90

    # Delays (seconds)
    request_delay: float = 1.0

    # Headers
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


config = CrawlerConfig()
