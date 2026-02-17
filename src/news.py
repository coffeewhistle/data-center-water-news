import logging
from newsapi import NewsApiClient
from src.config import NEWS_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NewsFetcher:
    def __init__(self):
        if not NEWS_API_KEY:
            logger.warning("NEWS_API_KEY is not set. News fetching will fail.")
            self.news_api = None
        else:
            self.news_api = NewsApiClient(api_key=NEWS_API_KEY)

    def fetch_articles(self, existing_urls=None):
        """
        Fetches articles from NewsAPI, filtering out duplicates based on URL.

        Args:
            existing_urls (set or list): Collection of URLs already processed.

        Returns:
            list: A list of new article dictionaries.
        """
        if existing_urls is None:
            existing_urls = set()

        # Ensure existing_urls is a set for faster lookup
        existing_urls_set = set(existing_urls)
        new_articles = []

        if not self.news_api:
            logger.error("NewsApiClient not initialized. Cannot fetch articles.")
            return []

        try:
            # Query: (data center AND water)
            # Language: en
            # Sort by: publishedAt
            response = self.news_api.get_everything(
                q="(data center AND water)", language="en", sort_by="publishedAt"
            )

            if response["status"] != "ok":
                logger.error(f"NewsAPI returned status: {response.get('status')}")
                return []

            articles = response.get("articles", [])
            logger.info(f"Fetched {len(articles)} articles from NewsAPI.")

            for article in articles:
                url = article.get("url")
                if url and url not in existing_urls_set:
                    new_articles.append(article)
                    # existing_urls_set.add(url) # Optional: if we want to dedup within the same fetch, but prompt says "existing_urls"

            logger.info(f"Found {len(new_articles)} new unique articles.")
            return new_articles

        except Exception as e:
            logger.error(f"Error fetching articles: {e}")
            return []
