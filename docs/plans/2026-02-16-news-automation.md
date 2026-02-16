# Data Center & Water News Automation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build an automated system to fetch news about "data centers" and "water", extract insights using Gemini 1.5 Pro, store them in Google Sheets, and send a WhatsApp briefing via Twilio.

**Architecture:**
- **Modular Python Scripts:** Separate modules for News, Intelligence, Storage, Notification.
- **Configuration:** Hybrid approach supporting `config.yaml` (local) and Environment Variables (GitHub Actions).
- **Automation:** GitHub Actions workflow running daily at 8:00 AM PT.

**Tech Stack:** `newsapi-python`, `google-generativeai`, `gspread`, `oauth2client`, `twilio`, `pyyaml`.

---

### Task 1: Project Setup & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `src/__init__.py`

**Step 1: Create requirements.txt**
Define dependencies: `newsapi-python`, `google-generativeai`, `gspread`, `oauth2client`, `twilio`, `pyyaml`.

**Step 2: Create .gitignore**
Exclude: `venv/`, `__pycache__/`, `*.pyc`, `config.yaml`, `credentials.json`, `.env`.

**Step 3: Commit**
`git add . && git commit -m "chore: initial project setup"`

---

### Task 2: Configuration Management

**Files:**
- Create: `src/config.py`
- Create: `config.yaml.template`

**Step 1: Create config.yaml.template**
Template for API keys: `NEWS_API_KEY`, `GEMINI_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_WHATSAPP`, `TWILIO_TO_WHATSAPP`, `GOOGLE_SHEET_ID`, `GOOGLE_CREDENTIALS_JSON`.

**Step 2: Implement src/config.py**
- Load `config.yaml` if it exists.
- Expose configuration values as constants or a dictionary.
- Prioritize Environment Variables for GitHub Actions compatibility.

**Step 3: Commit**
`git add src/config.py config.yaml.template && git commit -m "feat: configuration management"`

---

### Task 3: Google Sheets Storage & Deduplication

**Files:**
- Create: `src/storage.py`
- Test: `tests/test_storage_mock.py` (Mocking gspread)

**Step 1: Implement StorageManager class**
- Method `__init__`: Authenticate with `gspread` using service account credentials (from string or file).
- Method `get_existing_urls()`: Fetch all URLs from Column C (Url).
- Method `save_article(article_data)`: Append a row with Date, Title, URL, Summary, Author, Entities.

**Step 2: Verify with a simple script (Manual verification required as we can't easily mock API without credentials)**
Create a temporary `test_sheets.py` to try connecting (skipping if no credentials yet).

**Step 3: Commit**
`git add src/storage.py && git commit -m "feat: google sheets storage and deduplication"`

---

### Task 4: News Fetching

**Files:**
- Create: `src/news.py`

**Step 1: Implement NewsFetcher class**
- Method `__init__`: Initialize `NewsApiClient`.
- Method `fetch_articles()`:
  - Query: `(data center AND water)`
  - Sort by: `publishedAt`
  - Language: `en`
  - Filter out articles with URLs present in `existing_urls` (passed from Storage).
  - Return list of new article objects.

**Step 2: Commit**
`git add src/news.py && git commit -m "feat: news fetching with deduplication"`

---

### Task 5: Intelligence Extraction (Gemini)

**Files:**
- Create: `src/intelligence.py`

**Step 1: Implement IntelligenceAgent class**
- Method `__init__`: Configure `genai` with API key.
- Method `analyze_article(article)`:
  - Construct prompt with article title + description/content.
  - Ask for JSON output: `{ "summary": "...", "author": "...", "entities": ["Company A (Connection Bio)", ...], "relevance_score": 1-10 }`
  - Return parsed JSON.

**Step 2: Commit**
`git add src/intelligence.py && git commit -m "feat: gemini intelligence extraction"`

---

### Task 6: WhatsApp Notification

**Files:**
- Create: `src/notification.py`

**Step 1: Implement Notifier class**
- Method `__init__`: Initialize Twilio Client.
- Method `send_briefing(articles)`:
  - Format message: "🌊 Data Center & Water Briefing 🌊\n\n1. [Title] - [Summary]...\n\n..."
  - Send via WhatsApp.

**Step 2: Commit**
`git add src/notification.py && git commit -m "feat: whatsapp notification"`

---

### Task 7: Orchestration

**Files:**
- Create: `main.py`

**Step 1: Implement main execution flow**
1. Load Config.
2. Initialize `StorageManager`, `NewsFetcher`, `IntelligenceAgent`, `Notifier`.
3. Get `existing_urls`.
4. Fetch `new_articles` (passing `existing_urls`).
5. If no new articles -> Send "No new updates" message -> Exit.
6. For each article:
   - Extract intelligence.
   - Save to Google Sheets.
   - Add to `briefing_list`.
7. Send "Morning Briefing" with top 3 articles.

**Step 2: Commit**
`git add main.py && git commit -m "feat: main orchestration script"`

---

### Task 8: GitHub Actions Automation

**Files:**
- Create: `.github/workflows/daily_briefing.yml`

**Step 1: Create workflow file**
- Trigger: `schedule` (cron: '0 15 * * *' -> 8am PT) and `workflow_dispatch`.
- Steps:
  - Checkout code.
  - Set up Python.
  - Install dependencies.
  - Create `credentials.json` from secret if needed (or pass as env var).
  - Run `python main.py`.
  - Env vars: Map secrets to environment variables matching `src/config.py`.

**Step 2: Commit**
`git add .github/workflows/daily_briefing.yml && git commit -m "ci: github actions workflow"`

