# Data Center & Water News Automation 🌊

Automated system to source, analyze, and report news about **Data Centers** and **Water Usage**.

## Features

1.  **News Sourcing**: Fetches articles from NewsAPI (TechCrunch, Reuters, Bloomberg, etc.) matching `("data center" AND "water")`.
2.  **Intelligence**: Uses **Gemini 1.5 Pro** to extract:
    *   3-sentence summary.
    *   Author & Entities involved.
    *   "Connection Bio" explaining the link between the entity and water/data centers.
3.  **Storage**: Deduplicates and saves structured data to **Google Sheets**.
4.  **Notification**: Sends a "Morning Briefing" via **WhatsApp (Twilio)** with the top 3 relevant articles.
5.  **Automation**: Runs daily at **8:00 AM PT** via GitHub Actions.

---

## 🚀 Setup Guide

### 1. Prerequisites
*   Python 3.9+
*   Google Cloud Project with Sheets API enabled.
*   Twilio Account (WhatsApp Sandbox or Live).
*   NewsAPI Key.
*   Gemini API Key.

### 2. Installation (Local)

```bash
# Clone the repository
git clone https://github.com/coffeewhistle/data-center-water-news.git
cd data-center-water-news

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create a `config.yaml` file in the root directory (use `config.yaml.template` as a reference):

```yaml
news_api:
  api_key: "YOUR_NEWS_API_KEY"

gemini:
  api_key: "YOUR_GEMINI_API_KEY"

twilio:
  account_sid: "YOUR_TWILIO_SID"
  auth_token: "YOUR_TWILIO_TOKEN"
  from_whatsapp: "whatsapp:+14155238886"
  to_whatsapp: "whatsapp:+1234567890"

google:
  sheet_id: "YOUR_GOOGLE_SHEET_ID"
  credentials_json: "credentials.json" # Path to local file
```

---

## 🔑 Google Sheets Setup

1.  **Create Project**: Go to [Google Cloud Console](https://console.cloud.google.com/).
2.  **Enable APIs**: Enable **"Google Sheets API"** and **"Google Drive API"**.
3.  **Service Account**:
    *   Go to **IAM & Admin > Service Accounts**.
    *   Create a new service account with **Editor** role.
    *   Create a JSON key and download it as `credentials.json`.
    *   Place `credentials.json` in the project root.
4.  **Share Sheet**:
    *   Create a Google Sheet.
    *   Share it with the `client_email` found in your `credentials.json`.
    *   Copy the Sheet ID from the URL (`docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit`).

---

## 🤖 GitHub Actions Automation

The workflow runs automatically at **8:00 AM PT**. To set it up:

1.  Go to your Repo **Settings > Secrets and variables > Actions**.
2.  Add the following **Repository Secrets**:

| Secret Name | Value |
|-------------|-------|
| `NEWS_API_KEY` | Your NewsAPI Key |
| `GEMINI_API_KEY` | Your Google Gemini API Key |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_FROM_WHATSAPP` | `whatsapp:+14155238886` |
| `TWILIO_TO_WHATSAPP` | Your WhatsApp number |
| `GOOGLE_SHEET_ID` | The ID of your Google Sheet |
| `GOOGLE_CREDENTIALS_JSON` | **Paste the entire content** of `credentials.json` |

---

## 🛠️ Usage

**Run Manually:**
```bash
python main.py
```

**Run via GitHub Actions:**
1.  Go to the **Actions** tab.
2.  Select **Daily News Briefing**.
3.  Click **Run workflow**.

---

## Project Structure

```
.
├── src/
│   ├── news.py           # NewsAPI integration & deduplication
│   ├── intelligence.py   # Gemini 1.5 Pro analysis
│   ├── storage.py        # Google Sheets management
│   ├── notification.py   # Twilio WhatsApp messaging
│   └── config.py         # Configuration loader
├── main.py               # Orchestration script
├── requirements.txt      # Dependencies
└── .github/workflows/    # Automation schedule
```
