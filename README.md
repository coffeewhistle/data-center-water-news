# Data Center News Leads Generator

This project automates the discovery and extraction of news articles related to data centers, cooling, and water usage, storing leads in BigQuery.

## Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration:**
   - Edit `config.py` to set your BigQuery Project ID and Dataset ID if different from defaults.
   - Set environment variable `GOOGLE_APPLICATION_CREDENTIALS` to your service account key path.
   - For LLM extraction, ensure you have the appropriate API keys set (e.g. `ABACUS_API_KEY`).

3. **Database Initialization:**
   The `main.py` script automatically creates the dataset `dc_news_leads` and tables if they don't exist.

## Usage

Run the pipeline:

```bash
python main.py
```

`main.py` is now state-driven:
- If backfill is not complete, it ingests the next backfill window and advances `ingestion_state.backfill_progress_cutoff`.
- Once backfill completes, it switches to daily mode and ingests up to `DAILY_CATCHUP_MAX_DAYS` at a time until caught up.
- The run window is tracked in `ingestion_state` and resumed on next execution.

Recommended scheduling:
- Run `python main.py` from cron/Task Scheduler at least daily.
- During initial backfill, run more frequently for faster catch-up.

## File Structure
- `main.py`: Entry point for the pipeline.
- `db.py`: BigQuery interaction layer.
- `news_fetcher.py`: Fetches articles from Google News RSS.
- `extractor.py`: Handles content extraction (LLM integration).
- `config.py`: Configuration constants.
