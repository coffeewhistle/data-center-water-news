import gspread
import logging
from src import config

logger = logging.getLogger(__name__)


class StorageManager:
    def __init__(self):
        """
        Initialize the StorageManager with Google Sheets credentials.
        """
        self.gc = None
        self.sh = None
        self.worksheet = None

        try:
            if not config.GOOGLE_CREDENTIALS:
                raise ValueError("GOOGLE_CREDENTIALS not found in configuration.")

            self.gc = gspread.service_account_from_dict(config.GOOGLE_CREDENTIALS)

            if not config.GOOGLE_SHEET_ID:
                raise ValueError("GOOGLE_SHEET_ID not found in configuration.")

            # Open the spreadsheet by key
            self.sh = self.gc.open_by_key(config.GOOGLE_SHEET_ID)

            # Select the first worksheet by default
            self.worksheet = self.sh.get_worksheet(0)

        except (
            gspread.exceptions.SpreadsheetNotFound,
            gspread.exceptions.APIError,
            ValueError,
        ) as e:
            logger.error(f"Failed to initialize StorageManager: {e}")
            raise

    def get_existing_urls(self):
        """
        Fetch all URLs from Column C (index 3).
        Returns a set of URLs.
        """
        try:
            # Column C is index 3. col_values uses 1-based index in gspread?
            # gspread documentation says: col_values(col) where col is integer.
            # "Column C" is the 3rd column.
            urls = self.worksheet.col_values(3)

            # Assuming the first row might be a header "URL"
            if urls and urls[0].lower() == "url":
                urls = urls[1:]

            return set(urls)
        except gspread.exceptions.APIError as e:
            logger.error(f"Error fetching existing URLs: {e}")
            raise

    def save_article(self, article_data):
        """
        Append a row with [Date, Title, URL, Summary, Author, Entities].
        article_data: dict containing the keys.
        """
        try:
            row = [
                article_data.get("date", ""),
                article_data.get("title", ""),
                article_data.get("url", ""),
                article_data.get("summary", ""),
                article_data.get("author", ""),
                article_data.get("entities", ""),
            ]
            self.worksheet.append_row(row)
            logger.info(f"Saved article: {article_data.get('title', 'Unknown Title')}")
        except gspread.exceptions.APIError as e:
            logger.error(f"Error saving article: {e}")
            raise
