# backend/app/crawler/discovery.py
import asyncio
from typing import Callable, List, Optional, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from app.crawler.config import config
from app.crawler.extractor import HTMLExtractor


class SiteDiscovery:
    """Discover all URLs within a domain (homepage + sitemap + BFS 2 levels)"""

    def __init__(self):
        self.extractor = HTMLExtractor()

    async def discover(
        self,
        start_url: str,
        on_progress: Optional[Callable[[int, str], None]] = None
    ) -> List[str]:
        """
        Find all unique URLs in the same domain as start_url.
        Steps:
          1. Fetch homepage → collect links
          2. Try /sitemap.xml → collect <loc> URLs
          3. BFS up to depth 2 on found URLs → collect more links
        Returns sorted list of unique URLs.
        """
        parsed = urlparse(start_url)
        if not parsed.netloc or parsed.scheme not in ('http', 'https'):
            raise ValueError(f"Invalid URL: {start_url!r}. Must be an http/https URL with a domain.")
        domain = parsed.netloc
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        found: Set[str] = set()
        visited: Set[str] = set()

        def log(url: str):
            found.add(url)
            if on_progress:
                on_progress(len(found), url)

        # Step 1: homepage
        html = await self.extractor.fetch_html(start_url)
        if html:
            for link in self._extract_links(html, start_url, domain):
                if link not in found:
                    log(link)
        visited.add(start_url)
        log(start_url)

        # Step 2: sitemap.xml
        sitemap_url = f"{base_url}/sitemap.xml"
        sitemap_html = await self.extractor.fetch_html(sitemap_url)
        if sitemap_html:
            for link in self._extract_sitemap_urls(sitemap_html, domain):
                if link not in found:
                    log(link)

        # Step 3: BFS depth 2
        # Depth 1: crawl all URLs found so far (from homepage + sitemap)
        depth1_queue = sorted(found - visited)[:200]
        depth2_urls: Set[str] = set()

        for url in depth1_queue:
            if url in visited:
                continue
            visited.add(url)
            await asyncio.sleep(config.request_delay)
            html = await self.extractor.fetch_html(url)
            if not html:
                continue
            for link in self._extract_links(html, url, domain):
                if link not in found:
                    log(link)
                    depth2_urls.add(link)
                if len(found) >= 1000:
                    break
            if len(found) >= 1000:
                break

        # Depth 2: crawl URLs discovered during depth 1
        if len(found) < 1000:
            for url in sorted(depth2_urls - visited)[:200]:
                if url in visited:
                    continue
                visited.add(url)
                await asyncio.sleep(config.request_delay)
                html = await self.extractor.fetch_html(url)
                if not html:
                    continue
                for link in self._extract_links(html, url, domain):
                    if link not in found:
                        log(link)
                    if len(found) >= 1000:
                        break
                if len(found) >= 1000:
                    break

        return sorted(found)

    def _extract_links(self, html: str, base_url: str, domain: str) -> List[str]:
        """Parse <a href> tags, return same-domain URLs only."""
        soup = BeautifulSoup(html, 'lxml')
        links = []
        for tag in soup.find_all('a', href=True):
            url = urljoin(base_url, tag['href'])
            parsed = urlparse(url)
            if parsed.netloc == domain and parsed.scheme in ('http', 'https'):
                # Strip fragment
                clean = url.split('#')[0].rstrip('/')
                if clean and clean not in links:
                    links.append(clean)
        return links

    def _extract_sitemap_urls(self, xml: str, domain: str) -> List[str]:
        """Parse sitemap XML, return same-domain <loc> URLs."""
        soup = BeautifulSoup(xml, 'lxml-xml')
        urls = []
        for loc in soup.find_all('loc'):
            url = loc.get_text(strip=True)
            if urlparse(url).netloc == domain:
                urls.append(url.rstrip('/'))
        return urls
