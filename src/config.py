import os
import json
import yaml
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants for configuration keys
KEY_NEWS_API_KEY = "NEWS_API_KEY"
KEY_GEMINI_API_KEY = "GEMINI_API_KEY"
KEY_TWILIO_ACCOUNT_SID = "TWILIO_ACCOUNT_SID"
KEY_TWILIO_AUTH_TOKEN = "TWILIO_AUTH_TOKEN"
KEY_TWILIO_FROM_WHATSAPP = "TWILIO_FROM_WHATSAPP"
KEY_TWILIO_TO_WHATSAPP = "TWILIO_TO_WHATSAPP"
KEY_GOOGLE_SHEET_ID = "GOOGLE_SHEET_ID"
KEY_GOOGLE_CREDENTIALS_JSON = "GOOGLE_CREDENTIALS_JSON"


def load_config():
    """
    Loads configuration from environment variables and config.yaml.
    Environment variables take precedence.
    """
    config_data = {}

    # Load from config.yaml if it exists
    config_path = "config.yaml"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    config_data.update(yaml_config)
        except Exception as e:
            logger.warning(f"Error loading config.yaml: {e}")

    # Helper to get value from env or config
    def get_value(key, default=None):
        return os.environ.get(key) or config_data.get(key, default)

    # API Keys & Tokens
    news_api_key = get_value(KEY_NEWS_API_KEY)
    gemini_api_key = get_value(KEY_GEMINI_API_KEY)
    twilio_account_sid = get_value(KEY_TWILIO_ACCOUNT_SID)
    twilio_auth_token = get_value(KEY_TWILIO_AUTH_TOKEN)
    twilio_from_whatsapp = get_value(KEY_TWILIO_FROM_WHATSAPP)
    twilio_to_whatsapp = get_value(KEY_TWILIO_TO_WHATSAPP)
    google_sheet_id = get_value(KEY_GOOGLE_SHEET_ID)

    # Google Credentials Handling
    google_credentials_raw = get_value(KEY_GOOGLE_CREDENTIALS_JSON)
    google_credentials = None

    if google_credentials_raw:
        # 1. Try to load as JSON string first
        try:
            parsed_creds = json.loads(google_credentials_raw)
            if isinstance(parsed_creds, dict):
                google_credentials = parsed_creds
            else:
                # If valid JSON but not a dict (e.g. a string "filename.json"), treat as potential file path
                logger.debug(
                    "GOOGLE_CREDENTIALS_JSON parsed as JSON but not a dict. Checking as file path."
                )
                raise json.JSONDecodeError("Not a dict", google_credentials_raw, 0)
        except json.JSONDecodeError:
            # 2. If not a valid JSON dict, check if it's a file path
            if os.path.exists(google_credentials_raw):
                try:
                    with open(google_credentials_raw, "r") as f:
                        google_credentials = json.load(f)
                except Exception as e:
                    logger.warning(
                        f"Error reading Google Credentials file '{google_credentials_raw}': {e}"
                    )
            else:
                logger.warning(
                    f"GOOGLE_CREDENTIALS_JSON is not a valid JSON string and file '{google_credentials_raw}' does not exist."
                )
        except Exception as e:
            logger.warning(f"Unexpected error processing GOOGLE_CREDENTIALS_JSON: {e}")

    return {
        KEY_NEWS_API_KEY: news_api_key,
        KEY_GEMINI_API_KEY: gemini_api_key,
        KEY_TWILIO_ACCOUNT_SID: twilio_account_sid,
        KEY_TWILIO_AUTH_TOKEN: twilio_auth_token,
        KEY_TWILIO_FROM_WHATSAPP: twilio_from_whatsapp,
        KEY_TWILIO_TO_WHATSAPP: twilio_to_whatsapp,
        KEY_GOOGLE_SHEET_ID: google_sheet_id,
        "GOOGLE_CREDENTIALS": google_credentials,
    }


# Load configuration once
_config = load_config()

# Expose as constants
NEWS_API_KEY = _config.get(KEY_NEWS_API_KEY)
GEMINI_API_KEY = _config.get(KEY_GEMINI_API_KEY)
TWILIO_ACCOUNT_SID = _config.get(KEY_TWILIO_ACCOUNT_SID)
TWILIO_AUTH_TOKEN = _config.get(KEY_TWILIO_AUTH_TOKEN)
TWILIO_FROM_WHATSAPP = _config.get(KEY_TWILIO_FROM_WHATSAPP)
TWILIO_TO_WHATSAPP = _config.get(KEY_TWILIO_TO_WHATSAPP)
GOOGLE_SHEET_ID = _config.get(KEY_GOOGLE_SHEET_ID)
GOOGLE_CREDENTIALS = _config.get("GOOGLE_CREDENTIALS")
