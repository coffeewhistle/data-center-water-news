import unittest
from unittest.mock import MagicMock, patch
from src.news import NewsFetcher


class TestNewsFetcher(unittest.TestCase):
    def setUp(self):
        # Patch NEWS_API_KEY to ensure NewsFetcher initializes
        self.config_patcher = patch("src.news.NEWS_API_KEY", "dummy_key")
        self.config_patcher.start()

        # Patch the NewsApiClient in src.news to avoid actual API calls
        self.patcher = patch("src.news.NewsApiClient")
        self.MockNewsApiClient = self.patcher.start()

        # Setup the mock instance
        self.mock_api_instance = self.MockNewsApiClient.return_value

        # Create an instance of NewsFetcher
        self.fetcher = NewsFetcher()

    def tearDown(self):
        self.patcher.stop()
        self.config_patcher.stop()

    def test_fetch_articles_deduplication(self):
        # Mock response from get_everything
        mock_response = {
            "status": "ok",
            "articles": [
                {
                    "title": "Article 1",
                    "url": "http://example.com/1",
                    "publishedAt": "2023-01-01T10:00:00Z",
                },
                {
                    "title": "Article 2",
                    "url": "http://example.com/2",
                    "publishedAt": "2023-01-01T11:00:00Z",
                },
                {
                    "title": "Article 3",
                    "url": "http://example.com/3",
                    "publishedAt": "2023-01-01T12:00:00Z",
                },
            ],
        }
        self.mock_api_instance.get_everything.return_value = mock_response

        # Existing URLs - verify 'http://example.com/2' is filtered out
        existing_urls = {"http://example.com/2", "http://example.com/old"}

        new_articles = self.fetcher.fetch_articles(existing_urls)

        # Assertions
        self.assertEqual(len(new_articles), 2)
        self.assertEqual(new_articles[0]["url"], "http://example.com/1")
        self.assertEqual(new_articles[1]["url"], "http://example.com/3")

        # Verify get_everything arguments
        self.mock_api_instance.get_everything.assert_called_once_with(
            q="(data center AND water)", language="en", sort_by="publishedAt"
        )

    def test_fetch_articles_api_error(self):
        # Simulate an exception raising from get_everything
        self.mock_api_instance.get_everything.side_effect = Exception(
            "API connection failed"
        )

        new_articles = self.fetcher.fetch_articles([])

        # Should handle error gracefully and return empty list
        self.assertEqual(new_articles, [])

    def test_fetch_articles_no_articles(self):
        mock_response = {"status": "ok", "articles": []}
        self.mock_api_instance.get_everything.return_value = mock_response

        new_articles = self.fetcher.fetch_articles([])
        self.assertEqual(new_articles, [])

    def test_init_without_api_key(self):
        # Temporarily unset NEWS_API_KEY in src.config (mocking it)
        with patch("src.news.NEWS_API_KEY", None):
            fetcher_no_key = NewsFetcher()
            result = fetcher_no_key.fetch_articles([])
            self.assertEqual(result, [])
            # Verify NewsApiClient was NOT initialized (or handle it)
            # In my implementation, I check for api_key in __init__ or handle it gracefully.


if __name__ == "__main__":
    unittest.main()
