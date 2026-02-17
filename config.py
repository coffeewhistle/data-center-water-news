import os
from datetime import date

# BigQuery Configuration
PROJECT_ID = os.getenv("PROJECT_ID", "emergence-database")
DATASET_ID = os.getenv("DATASET_ID", "dc_news_leads")

# Table Names
TABLE_ARTICLES = "articles"
TABLE_PEOPLE = "people"
TABLE_COMPANIES = "companies"
TABLE_ARTICLE_PEOPLE = "article_people"
TABLE_INGESTION_STATE = "ingestion_state"
TABLE_EXTRACTION_FAILURES = "extraction_failures"

# Search Configuration
KEYWORDS = [
    "data center",
    "data centre",
    "hyperscale data center",
    "colocation data center",
    "data center cooling",
    "data center water usage",
    "data center sustainability"
]
FETCH_CONCURRENCY = 4
EXTRACTION_CONCURRENCY = 6
HTTP_TIMEOUT_SECONDS = 20

# Date Configuration
BACKFILL_START_DATE = "2025-01-01"
BACKFILL_WINDOW_DAYS = 7
DAILY_CATCHUP_MAX_DAYS = 3
PIPELINE_FETCH_LIMIT = 60
PIPELINE_LOCK_LEASE_SECONDS = 3600

# Abacus AI Configuration
ABACUS_API_KEY = os.getenv("ABACUS_API_KEY")


def _env_int(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


FETCH_CONCURRENCY = _env_int("FETCH_CONCURRENCY", FETCH_CONCURRENCY)
EXTRACTION_CONCURRENCY = _env_int("EXTRACTION_CONCURRENCY", EXTRACTION_CONCURRENCY)
HTTP_TIMEOUT_SECONDS = _env_int("HTTP_TIMEOUT_SECONDS", HTTP_TIMEOUT_SECONDS)
BACKFILL_WINDOW_DAYS = _env_int("BACKFILL_WINDOW_DAYS", BACKFILL_WINDOW_DAYS)
DAILY_CATCHUP_MAX_DAYS = _env_int("DAILY_CATCHUP_MAX_DAYS", DAILY_CATCHUP_MAX_DAYS)
PIPELINE_FETCH_LIMIT = _env_int("PIPELINE_FETCH_LIMIT", PIPELINE_FETCH_LIMIT)
PIPELINE_LOCK_LEASE_SECONDS = _env_int("PIPELINE_LOCK_LEASE_SECONDS", PIPELINE_LOCK_LEASE_SECONDS)
BACKFILL_START_DATE = os.getenv("BACKFILL_START_DATE", BACKFILL_START_DATE)


def validate_config():
    errors = []

    if not PROJECT_ID.strip():
        errors.append("PROJECT_ID must be non-empty.")
    if not DATASET_ID.strip():
        errors.append("DATASET_ID must be non-empty.")

    for name, value in [
        ("FETCH_CONCURRENCY", FETCH_CONCURRENCY),
        ("EXTRACTION_CONCURRENCY", EXTRACTION_CONCURRENCY),
        ("HTTP_TIMEOUT_SECONDS", HTTP_TIMEOUT_SECONDS),
        ("BACKFILL_WINDOW_DAYS", BACKFILL_WINDOW_DAYS),
        ("DAILY_CATCHUP_MAX_DAYS", DAILY_CATCHUP_MAX_DAYS),
        ("PIPELINE_FETCH_LIMIT", PIPELINE_FETCH_LIMIT),
        ("PIPELINE_LOCK_LEASE_SECONDS", PIPELINE_LOCK_LEASE_SECONDS),
    ]:
        if value <= 0:
            errors.append(f"{name} must be > 0.")

    try:
        date.fromisoformat(BACKFILL_START_DATE)
    except ValueError:
        errors.append("BACKFILL_START_DATE must be YYYY-MM-DD.")

    if errors:
        raise ValueError("Invalid configuration: " + "; ".join(errors))
