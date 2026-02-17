import logging
import os
from twilio.rest import Client
from src.config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_FROM_WHATSAPP,
    TWILIO_TO_WHATSAPP,
)

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self):
        """
        Initialize the Twilio client using configuration from src.config.
        """
        self.client = None
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            logger.warning(
                "Twilio credentials not found in configuration. Messages will not be sent."
            )
        else:
            try:
                self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")

    def send_briefing(self, articles):
        """
        Formats and sends a WhatsApp briefing for the provided articles.

        Args:
            articles (list): A list of tuples (article, intelligence_data).
        """
        if not self.client:
            logger.error("Twilio client is not initialized. Cannot send briefing.")
            return

        if not articles:
            message_body = "No new articles found today."
        else:
            # Format the message header
            message_body = "🌊 Data Center & Water Briefing 🌊\n\n"

            # Take top 3 articles
            top_articles = articles[:3]

            for i, (article, intelligence) in enumerate(top_articles, 1):
                title = article.get("title", "No Title")

                # Extract summary from intelligence data
                summary = "No summary available."
                if isinstance(intelligence, dict):
                    # Try 'summary' first, then look for other potential keys
                    summary = intelligence.get(
                        "summary", intelligence.get("brief", "No summary available.")
                    )
                elif isinstance(intelligence, str):
                    summary = intelligence

                url = article.get("url", "No URL")

                # Format each article entry
                entry = f"{i}. *{title}*\nSummary: {summary}\nLink: {url}\n\n"
                message_body += entry

        try:
            # Twilio WhatsApp numbers usually require 'whatsapp:' prefix if not already present
            from_number = TWILIO_FROM_WHATSAPP
            to_number = TWILIO_TO_WHATSAPP

            if from_number and not from_number.startswith("whatsapp:"):
                from_number = f"whatsapp:{from_number}"
            if to_number and not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"

            message = self.client.messages.create(
                from_=from_number, to=to_number, body=message_body.strip()
            )
            logger.info(f"Briefing sent successfully. SID: {message.sid}")
            return message.sid
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return None
