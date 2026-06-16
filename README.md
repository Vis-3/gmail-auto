# Gmail Triage & Reply Assistant

A personal automation tool that monitors Gmail, classifies incoming emails using an LLM, sends Telegram notifications with reply options, and drafts replies using full thread context — all running locally with no external server required.

## What It Does

1. **Polls Gmail** every hour for unread emails in the inbox
2. **Classifies each email** using a two-tier pipeline: rule-based pre-filter first, LLM fallback for ambiguous cases
3. **Sends a Telegram notification** with sender, subject, category, and rationale — along with Reply / No Reply inline buttons
4. **Drafts a reply** using the full thread history when you tap Reply, and saves it directly to Gmail Drafts
5. **Tracks state** for every email in a local SQLite database (`new → classified → notified → drafted → read_complete`)

## Architecture

```
Gmail API (poll every 1hr)
        │
        ▼
  email_fetcher.py  ──►  llm_classifier.py  ──►  notifier.py
                                │                      │
                          SQLite (app.db)        Telegram Bot
                                                       │
                          email_drafter.py  ◄──────────┘
                          (on Reply tap)
                                │
                          Gmail Drafts
```

**Components:**
| File | Responsibility |
|---|---|
| `email_fetcher.py` | Gmail OAuth, message parsing, thread retrieval |
| `llm_classifier.py` | Rule-based filter + Groq LLM classification (Pydantic output) |
| `notifier.py` | Telegram bot, inline keyboard, callback handling |
| `email_drafter.py` | Thread-aware LLM draft generation, save to Gmail Drafts |
| `models.py` | SQLite schema and all database operations |
| `main.py` | Async orchestration — `asyncio.gather` runs poller and bot concurrently |
| `config.py` | Environment variable loading with guards |

## Classification Categories

| Category | How it's assigned |
|---|---|
| `job_update` | LLM — application updates, recruiter outreach |
| `university` | Rule — sender contains `@iu.edu` |
| `conversation` | Rule — sender is in your 30-day sent-mail history |
| `informational` | LLM — newsletters, announcements, FYIs |
| `noise` | Rule — known job portal / ad domains; otherwise LLM |

The rule-based tier handles clear-cut cases instantly (zero LLM cost). Only ambiguous emails hit the Groq API.

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12 |
| Package manager | [uv](https://github.com/astral-sh/uv) |
| Gmail | Google Gmail API v1 (OAuth 2.0) |
| LLM | Groq API — `llama-3.3-70b-versatile` (free tier) |
| Structured output | Pydantic `BaseModel` |
| Notifications | Telegram Bot API (python-telegram-bot) |
| Database | SQLite via `sqlite3` |
| Async | `asyncio.gather` |
| Observability | Langfuse (LLM call tracing) |
| Auto-start | Windows Task Scheduler |
| Testing | pytest |
| CI | GitHub Actions |

## Setup

### Prerequisites

- Python 3.12+
- A Google Cloud project with the Gmail API enabled
- A Groq API key — free at [console.groq.com](https://console.groq.com)
- A Telegram bot token — from [@BotFather](https://t.me/botfather)

### 1. Clone and install

```bash
git clone <repo-url>
cd Gmail_Auto
uv sync
```

### 2. Enable the Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → **APIs & Services → Enable APIs** → search **Gmail API** → Enable
3. **Credentials → Create Credentials → OAuth 2.0 Client ID** (Desktop app type)
4. Download the JSON → save as `credentials.json` in the project root
5. **OAuth consent screen → Test users** → add your Gmail address

### 3. Create a Telegram bot

1. Message [@BotFather](https://t.me/botfather) on Telegram → `/newbot`
2. Copy the bot token
3. Start a conversation with your new bot, then open:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
4. Send any message to your bot, refresh the URL, and copy your `id` from the `chat` object

### 4. Environment variables

Create `.env` in the project root:

```env
GROQ_API_KEY=gsk_...
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Optional — Langfuse LLM observability (leave blank to disable tracing)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

Get your Langfuse keys from [cloud.langfuse.com](https://cloud.langfuse.com) (free tier). If the keys are absent, the `@observe()` decorators are silently skipped — nothing breaks.

### 5. Run

```bash
uv run main.py
```

### 6. Auto-start on login (Windows Task Scheduler)

Register `start.bat` to run automatically when you log in:

```cmd
schtasks /create /tn "GmailAuto" /tr "\"C:\Users\sansk\Documents\Spring-26\Gmail_Auto\start.bat\"" /sc onlogon /rl highest /f
```

To remove it later:

```cmd
schtasks /delete /tn "GmailAuto" /f
```

On first run a browser opens for Gmail OAuth consent. After authorizing, `token.json` is saved and all future runs authenticate silently (auto-refresh on expiry).

## Usage

Once running, leave the terminal open:

- Telegram notifications arrive within the next polling cycle (up to 1 hour) for each new unread email
- **Tap Reply** → a draft is generated from the thread history and saved to Gmail Drafts within seconds; the notification updates to confirm
- **Tap No Reply** → email is marked `read_complete` in the database; the notification updates to confirm
- Open **Gmail → Drafts**, review, edit as needed, and send

## Project Structure

```
Gmail_Auto/
├── main.py               # Entry point
├── email_fetcher.py      # Gmail API
├── llm_classifier.py     # Classification pipeline
├── notifier.py           # Telegram bot
├── email_drafter.py      # Draft generation
├── models.py             # SQLite
├── config.py             # Environment config
├── pyproject.toml        # Dependencies
├── tests/
│   ├── conftest.py       # Path setup for pytest
│   └── test_classifier.py
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions CI
├── Procfile              # Railway worker process definition
├── railway.toml          # Railway volume mount config
├── start.bat             # Windows Task Scheduler launcher (local)
├── credentials.json      # Google OAuth client secrets  (gitignored)
├── token.json            # OAuth access + refresh token (gitignored)
├── app.db                # SQLite database              (gitignored)
└── .env                  # Secrets                      (gitignored)
```

## Deploying to Railway

Railway runs the script 24/7 so you don't need your laptop on.

### 1. Encode your secrets as base64

In PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("credentials.json"))
[Convert]::ToBase64String([IO.File]::ReadAllBytes("token.json"))
```

### 2. Add environment variables in Railway dashboard

| Variable | Value |
|---|---|
| `CREDENTIALS_JSON_B64` | output of the first command above |
| `TOKEN_JSON_B64` | output of the second command above |
| `GROQ_API_KEY` | your Groq key |
| `TELEGRAM_BOT_TOKEN` | your bot token |
| `TELEGRAM_CHAT_ID` | your chat ID |
| `LANGFUSE_PUBLIC_KEY` | your Langfuse public key |
| `LANGFUSE_SECRET_KEY` | your Langfuse secret key |
| `LANGFUSE_BASE_URL` | your Langfuse base URL |
| `DB_PATH` | `/data/app.db` |

### 3. Add a volume

In Railway: **New → Volume** → mount path `/data`. This persists `app.db` across redeploys.

### 4. Deploy

Push to GitHub — Railway auto-deploys from the connected repo. The worker starts automatically.

> **Note:** `token.json` contains a refresh token that never expires as long as it's used. If Railway ever loses the decoded file (e.g. before the volume is mounted), re-run the base64 encode locally and update `TOKEN_JSON_B64`.

## Tests

Unit tests cover the classification pipeline — Pydantic schema validation, all rule-based filter paths, and the LLM call path (mocked):

```bash
uv run pytest tests/ -v
```

CI runs automatically on every push via GitHub Actions (`.github/workflows/ci.yml`). No secrets are required in CI — the Groq and Telegram keys are stubbed with dummy values since the LLM is mocked in tests.

## Security Notes

- `credentials.json`, `token.json`, `.env`, and `app.db` are all listed in `.gitignore` and are never committed to version control
- All secrets are loaded from environment variables — nothing is hardcoded
- `app.db` contains real email content and subject lines; handle accordingly
