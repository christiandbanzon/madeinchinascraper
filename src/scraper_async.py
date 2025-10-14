import asyncio
from typing import List, Tuple
import httpx
from bs4 import BeautifulSoup
from src.config import HEADERS, SEARCH_URL, REQUEST_DELAY


class AsyncScraper:
    def __init__(self, max_connections: int = 5):
        limits = httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_connections)
        self.client = httpx.AsyncClient(headers=HEADERS, limits=limits, timeout=20.0)

    async def close(self):
        await self.client.aclose()

    async def fetch_page(self, keyword: str, page: int) -> Tuple[List[str], int]:
        url = f"{SEARCH_URL}/{keyword}.html" if page == 1 else f"{SEARCH_URL}/{keyword}-p{page}.html"
        resp = await self.client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
        items = soup.select('.products-item, .product-item, .item, .product')
        return [url for url in [a.get('href') for a in soup.select('a') if a.get('href')] if url], len(items)

    async def fetch_pages(self, keyword: str, pages: int) -> List[Tuple[List[str], int]]:
        results = []
        sem = asyncio.Semaphore(5)

        async def worker(p: int):
            async with sem:
                out = await self.fetch_page(keyword, p)
                results.append(out)
                await asyncio.sleep(REQUEST_DELAY)

        await asyncio.gather(*(worker(p) for p in range(1, pages + 1)))
        return results





