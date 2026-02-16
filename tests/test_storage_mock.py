import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Create mock for gspread BEFORE importing src.storage
mock_gspread = MagicMock()


# Define exceptions as actual Exception subclasses so they can be caught
class MockSpreadsheetNotFound(Exception):
    pass


class MockAPIError(Exception):
    pass


mock_gspread.exceptions.SpreadsheetNotFound = MockSpreadsheetNotFound
mock_gspread.exceptions.APIError = MockAPIError
sys.modules["gspread"] = mock_gspread

# Add parent directory to path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage import StorageManager
# We don't need to import config here directly since we patch it inside src.storage


class TestStorageManager(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        mock_gspread.reset_mock()
        mock_gspread.service_account_from_dict.reset_mock()

    @patch("src.storage.config")
    def test_init_success(self, mock_config):
        # Setup mock config
        mock_config.GOOGLE_CREDENTIALS = {"key": "value"}
        mock_config.GOOGLE_SHEET_ID = "sheet_id_123"

        # Setup mock gspread client and sheet
        mock_gc = MagicMock()
        mock_sh = MagicMock()
        mock_ws = MagicMock()

        mock_gspread.service_account_from_dict.return_value = mock_gc
        mock_gc.open_by_key.return_value = mock_sh
        mock_sh.get_worksheet.return_value = mock_ws

        # Initialize
        manager = StorageManager()

        # Verify calls
        mock_gspread.service_account_from_dict.assert_called_with({"key": "value"})
        mock_gc.open_by_key.assert_called_with("sheet_id_123")
        mock_sh.get_worksheet.assert_called_with(0)

        self.assertEqual(manager.worksheet, mock_ws)

    @patch("src.storage.config")
    def test_init_missing_credentials(self, mock_config):
        mock_config.GOOGLE_CREDENTIALS = None

        with self.assertRaises(ValueError):
            StorageManager()

    @patch("src.storage.config")
    def test_get_existing_urls(self, mock_config):
        # Setup mocks
        mock_config.GOOGLE_CREDENTIALS = {"key": "value"}
        mock_config.GOOGLE_SHEET_ID = "sheet_id_123"

        mock_gc = MagicMock()
        mock_sh = MagicMock()
        mock_ws = MagicMock()

        mock_gspread.service_account_from_dict.return_value = mock_gc
        mock_gc.open_by_key.return_value = mock_sh
        mock_sh.get_worksheet.return_value = mock_ws

        manager = StorageManager()

        # Mock col_values return with header
        mock_ws.col_values.return_value = [
            "URL",
            "http://example.com/1",
            "http://example.com/2",
        ]

        urls = manager.get_existing_urls()

        # Verify
        mock_ws.col_values.assert_called_with(3)
        self.assertEqual(urls, {"http://example.com/1", "http://example.com/2"})

    @patch("src.storage.config")
    def test_save_article(self, mock_config):
        # Setup mocks
        mock_config.GOOGLE_CREDENTIALS = {"key": "value"}
        mock_config.GOOGLE_SHEET_ID = "sheet_id_123"

        mock_gc = MagicMock()
        mock_sh = MagicMock()
        mock_ws = MagicMock()

        mock_gspread.service_account_from_dict.return_value = mock_gc
        mock_gc.open_by_key.return_value = mock_sh
        mock_sh.get_worksheet.return_value = mock_ws

        manager = StorageManager()

        article_data = {
            "date": "2023-01-01",
            "title": "Test Title",
            "url": "http://test.com",
            "summary": "Test Summary",
            "author": "Test Author",
            "entities": "Test Entities",
        }

        manager.save_article(article_data)

        # Verify
        mock_ws.append_row.assert_called_with(
            [
                "2023-01-01",
                "Test Title",
                "http://test.com",
                "Test Summary",
                "Test Author",
                "Test Entities",
            ]
        )


if __name__ == "__main__":
    unittest.main()
