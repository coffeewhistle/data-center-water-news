import logging
import time
import sys
from src.storage import StorageManager
from src.news import NewsFetcher
from src.intelligence import IntelligenceAgent
from src.notification import Notifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting Data Center & Water News Automation")

    # 1. Initialize Storage
    try:
        storage_manager = StorageManager()
        existing_urls = storage_manager.get_existing_urls()
        logger.info(f"Loaded {len(existing_urls)} existing URLs.")
    except Exception as e:
        logger.error(f"Failed to initialize storage or retrieve URLs: {e}")
        return

    # 2. Fetch News
    try:
        news_fetcher = NewsFetcher()
        new_articles = news_fetcher.fetch_articles(existing_urls)
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        return

    if not new_articles:
        logger.info("No new articles found.")
        try:
            notifier = Notifier()
            # Passing empty list triggers "No new articles found today." message
            notifier.send_briefing([])
        except Exception as e:
            logger.error(f"Failed to send 'no news' notification: {e}")
        return

    logger.info(f"Found {len(new_articles)} new articles. Processing top 10...")

    # 3. Analyze and Save
    intelligence_agent = IntelligenceAgent()
    briefing_list = []

    # Process up to 10 articles to avoid rate limits
    articles_to_process = new_articles[:10]

    for article in articles_to_process:
        try:
            logger.info(f"Analyzing article: {article.get('title', 'Unknown')}")
            analysis = intelligence_agent.analyze_article(article)

            if not analysis:
                logger.warning(
                    f"Skipping article due to analysis failure: {article.get('url')}"
                )
                continue

            # Prepare data for storage
            # Merge article info with analysis info
            # Storage expects: date, title, url, summary, author, entities

            entities = analysis.get("entities", [])
            if isinstance(entities, list):
                entities_str = ", ".join(entities)
            else:
                entities_str = str(entities)

            save_data = {
                "date": article.get("publishedAt"),
                "title": article.get("title"),
                "url": article.get("url"),
                "summary": analysis.get("summary"),
                "author": analysis.get("author") or article.get("author"),
                "entities": entities_str,
            }

            storage_manager.save_article(save_data)
            briefing_list.append((article, analysis))

            # Rate limiting
            time.sleep(1)

        except Exception as e:
            logger.error(f"Error processing article {article.get('url')}: {e}")
            continue

    # 4. Notify
    if briefing_list:
        try:
            notifier = Notifier()
            # Send top 3 articles in the briefing
            notifier.send_briefing(briefing_list[:3])
            logger.info("Briefing sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send briefing: {e}")

    logger.info("Workflow completed successfully.")


if __name__ == "__main__":
    main()
