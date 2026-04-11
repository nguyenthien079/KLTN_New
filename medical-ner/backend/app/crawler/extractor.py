import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict
import trafilatura

from app.crawler.config import config


class HTMLExtractor:
    """Extract clean text from HTML"""

    async def fetch_html(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch HTML from URL"""
        # Full browser-like headers to avoid 406 errors
        headers = {
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url.strip(),  # Remove any trailing spaces
                    timeout=timeout,
                    headers=headers,
                    follow_redirects=True
                )
                response.raise_for_status()
                return response.text
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                return None

    def extract_clean_text(self, html: str) -> Dict[str, any]:
        """Extract clean text using trafilatura + BeautifulSoup"""
        # Try trafilatura first (best for article extraction)
        clean_text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False
        )

        if not clean_text:
            # Fallback: BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')

            # Remove script, style tags
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()

            clean_text = soup.get_text(separator=' ', strip=True)

        # Extract title
        soup = BeautifulSoup(html, 'lxml')
        title = soup.find('title')
        title_text = title.get_text(strip=True) if title else ""

        return {
            "title": title_text,
            "clean_text": clean_text or "",
            "char_count": len(clean_text) if clean_text else 0
        }
