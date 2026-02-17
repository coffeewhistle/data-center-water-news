import unittest
from unittest.mock import MagicMock, patch
from src.notification import Notifier
from src.config import TWILIO_FROM_WHATSAPP, TWILIO_TO_WHATSAPP


class TestNotifier(unittest.TestCase):
    @patch("src.notification.TWILIO_AUTH_TOKEN", "mock_token")
    @patch("src.notification.TWILIO_ACCOUNT_SID", "mock_sid")
    @patch("src.notification.Client")
    def test_send_briefing_with_articles(self, MockClient):
        # Setup mock
        mock_client_instance = MockClient.return_value
        mock_messages = mock_client_instance.messages
        mock_create = mock_messages.create
        mock_message = MagicMock()
        mock_message.sid = "SM12345"
        mock_create.return_value = mock_message

        notifier = Notifier()

        # Mock articles data
        articles = [
            (
                {"title": "Article 1", "url": "http://example.com/1"},
                {"summary": "Summary 1"},
            ),
            (
                {"title": "Article 2", "url": "http://example.com/2"},
                {"summary": "Summary 2"},
            ),
            (
                {"title": "Article 3", "url": "http://example.com/3"},
                {"summary": "Summary 3"},
            ),
            (
                {"title": "Article 4", "url": "http://example.com/4"},
                {"summary": "Summary 4"},
            ),
        ]

        # Call the method
        sid = notifier.send_briefing(articles)

        # Assertions
        self.assertEqual(sid, "SM12345")

        # Verify message body format
        expected_header = "🌊 Data Center & Water Briefing 🌊\n\n"

        # Check if create was called with correct arguments
        args, kwargs = mock_create.call_args
        self.assertIn("body", kwargs)
        self.assertTrue(kwargs["body"].startswith(expected_header))
        self.assertIn("1. *Article 1*", kwargs["body"])
        self.assertIn("2. *Article 2*", kwargs["body"])
        self.assertIn("3. *Article 3*", kwargs["body"])
        self.assertNotIn("4. *Article 4*", kwargs["body"])  # Only top 3

    @patch("src.notification.TWILIO_AUTH_TOKEN", "mock_token")
    @patch("src.notification.TWILIO_ACCOUNT_SID", "mock_sid")
    @patch("src.notification.Client")
    def test_send_briefing_no_articles(self, MockClient):
        # Setup mock
        mock_client_instance = MockClient.return_value
        mock_messages = mock_client_instance.messages
        mock_create = mock_messages.create
        mock_message = MagicMock()
        mock_message.sid = "SM67890"
        mock_create.return_value = mock_message

        notifier = Notifier()

        # Call with empty list
        sid = notifier.send_briefing([])

        # Assertions
        self.assertEqual(sid, "SM67890")

        # Check message body
        args, kwargs = mock_create.call_args
        self.assertEqual(kwargs["body"], "No new articles found today.")


if __name__ == "__main__":
    unittest.main()
