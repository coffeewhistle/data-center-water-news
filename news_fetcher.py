import feedparser
import urllib.parse
import config
from dateutil import parser
import datetime
from bs4 import BeautifulSoup
import asyncio
import httpx
from logging_utils import log_event, classify_error

class NewsFetcher:
    def __init__(self):
        self.base_url = "https://news.google.com/rss/search"

    async def fetch_articles(self, limit=30, client=None, start_date=None, end_date=None):
        owned_client = client is None
        if owned_client:
            timeout = httpx.Timeout(config.HTTP_TIMEOUT_SECONDS)
            client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

        try:
            semaphore = asyncio.Semaphore(config.FETCH_CONCURRENCY)
            tasks = [
                self._fetch_keyword_entries(
                    keyword=keyword,
                    client=client,
                    semaphore=semaphore,
                    start_date=start_date,
                    end_date=end_date,
                )
                for keyword in config.KEYWORDS
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            all_entries = []
            seen_urls = set()
            for batch in batch_results:
                if isinstance(batch, Exception):
                    continue
                for parsed in batch:
                    article_url = parsed.get("url")
                    if not article_url or article_url in seen_urls:
                        continue
                    seen_urls.add(article_url)
                    all_entries.append(parsed)
                    if len(all_entries) >= limit:
                        return all_entries
            return all_entries
        finally:
            if owned_client:
                await client.aclose()

    async def _fetch_keyword_entries(self, keyword, client, semaphore, start_date=None, end_date=None):
        query_text = keyword
        if start_date:
            query_text = f"{query_text} after:{start_date}"
        if end_date:
            query_text = f"{query_text} before:{end_date}"

        encoded_query = urllib.parse.quote(query_text)
        url = f"{self.base_url}?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        log_event("news_fetch_start", query=query_text, url=url)

        async with semaphore:
            response = await self._get_with_retry(client, url)
            if response is None:
                return []
            feed = feedparser.parse(response.text)

        entries = []
        for entry in feed.entries:
            parsed = self.parse_entry(entry)
            if parsed.get("url"):
                entries.append(parsed)
        log_event("news_fetch_done", query=query_text, entries=len(entries))
        return entries

    async def _get_with_retry(self, client, url, max_attempts=3, base_delay_seconds=1):
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response
            except Exception as exc:
                err_kind = classify_error(exc)
                is_last = attempt == max_attempts
                log_event(
                    "news_fetch_error",
                    level="ERROR",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error_type=type(exc).__name__,
                    error_kind=err_kind,
                    error=str(exc),
                    url=url,
                )
                if is_last or not err_kind.startswith("transient"):
                    return None
                await asyncio.sleep(base_delay_seconds * (2 ** (attempt - 1)))
        return None

    def parse_entry(self, entry):
        # Convert feedparser entry to a dict suitable for our pipeline
        published_dt = None
        if 'published' in entry:
            try:
                published_dt = parser.parse(entry.published)
            except Exception:
                published_dt = datetime.datetime.now()
        
        summary_html = entry.summary if 'summary' in entry else ""
        summary_text = BeautifulSoup(summary_html, "html.parser").get_text(" ", strip=True)
        
        return {
            "title": entry.title,
            "url": entry.link,
            "source_name": entry.source.title if 'source' in entry else "Unknown",
            "publish_datetime": published_dt,
            "summary": summary_text,
        }

if __name__ == "__main__":
    async def _main():
        fetcher = NewsFetcher()
        articles = await fetcher.fetch_articles(limit=5)
        for article in articles:
            print(article)

    asyncio.run(_main())
