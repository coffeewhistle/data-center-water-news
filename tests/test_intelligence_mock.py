import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add the project root to sys.path so we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.intelligence import IntelligenceAgent


class TestIntelligenceAgent(unittest.TestCase):
    @patch("src.intelligence.genai")
    @patch("src.intelligence.GEMINI_API_KEY", "fake_key")
    def test_init(self, mock_genai):
        agent = IntelligenceAgent()
        mock_genai.configure.assert_called_with(api_key="fake_key")
        mock_genai.GenerativeModel.assert_called_with("gemini-1.5-pro")

    @patch("src.intelligence.genai")
    @patch("src.intelligence.GEMINI_API_KEY", "fake_key")
    def test_analyze_article_success(self, mock_genai):
        agent = IntelligenceAgent()

        # Mock the response object
        mock_response = MagicMock()
        expected_json = {
            "summary": "This is a summary.",
            "author": "John Doe",
            "entities": ["Google (Tech Giant)"],
            "relevance_score": 8,
        }
        mock_response.text = json.dumps(expected_json)

        # Mock the model's generate_content method
        mock_model = mock_genai.GenerativeModel.return_value
        mock_model.generate_content.return_value = mock_response

        article = {"title": "Test Title", "content": "Test Content"}
        result = agent.analyze_article(article)

        self.assertEqual(result, expected_json)
        mock_model.generate_content.assert_called()

    @patch("src.intelligence.genai")
    @patch("src.intelligence.GEMINI_API_KEY", "fake_key")
    def test_analyze_article_json_error(self, mock_genai):
        agent = IntelligenceAgent()

        mock_response = MagicMock()
        mock_response.text = "Invalid JSON"

        mock_model = mock_genai.GenerativeModel.return_value
        mock_model.generate_content.return_value = mock_response

        article = {"title": "Test Title", "content": "Test Content"}
        result = agent.analyze_article(article)

        self.assertIsNone(result)

    @patch("src.intelligence.genai")
    @patch("src.intelligence.GEMINI_API_KEY", "fake_key")
    def test_analyze_article_generation_error_fallback(self, mock_genai):
        agent = IntelligenceAgent()

        # Mock the primary model to raise an exception
        mock_primary_model = MagicMock()
        mock_primary_model.generate_content.side_effect = Exception("API Error")

        # Mock the fallback model to succeed
        mock_fallback_model = MagicMock()
        mock_response = MagicMock()
        expected_json = {
            "summary": "Fallback success",
            "author": "Jane Doe",
            "entities": [],
            "relevance_score": 5,
        }
        mock_response.text = json.dumps(expected_json)
        mock_fallback_model.generate_content.return_value = mock_response

        # Setup the side effects for GenerativeModel constructor
        # First call returns primary, second call returns fallback
        # Wait, inside __init__ it calls GenerativeModel('gemini-1.5-pro') -> returns mock_primary_model
        # Then inside analyze_article exception handler, it calls GenerativeModel('gemini-1.5-flash') -> returns mock_fallback_model

        def side_effect(model_name):
            if model_name == "gemini-1.5-pro":
                return mock_primary_model
            elif model_name == "gemini-1.5-flash":
                return mock_fallback_model
            return MagicMock()

        mock_genai.GenerativeModel.side_effect = side_effect

        # Re-init agent to pick up the side effect
        agent = IntelligenceAgent()

        article = {"title": "Test Title", "content": "Test Content"}
        result = agent.analyze_article(article)

        self.assertEqual(result, expected_json)
        # Verify both models were called
        mock_primary_model.generate_content.assert_called()
        mock_fallback_model.generate_content.assert_called()


if __name__ == "__main__":
    unittest.main()
