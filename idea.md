# Telegram Chat Summarizer Bot — Project Specification

## Goal

Build a Python Telegram bot that:
1. Collects all messages from groups/supergroups it is added to.
2. Generates a **daily Russian-language summary** of discussions, **grouped by themes**, using the Google Gemini API.
3. Sends the summary as a **direct message** to every user who subscribed to the bot, every day at a fixed time.
4. Saves all **images** and **links** posted in those chats to **Yandex Disk**, organized by date.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Telegram library | `python-telegram-bot` (v21+, async) |
| LLM for summarization | **Google Gemini API** (free tier, model `gemini-1.5-flash` or newer) |
| Cloud storage | **Yandex Disk** (REST API via `yadisk` library or `requests`) |
| Database | **SQLite** (via `aiosqlite` or `SQLAlchemy` async) |
| Scheduler | `APScheduler` (AsyncIOScheduler) |
| Config | `.env` file via `python-dotenv` |
| Containerization | **Docker + docker-compose** |
| Logging | Python `logging` module + rotating file handler |

---

## Functional Requirements

### 1. Message Collection

- Bot is added to a group/supergroup as an **admin** (or with privacy mode disabled).
- On every incoming message, save to SQLite:
  - `chat_id`, `chat_title`, `chat_type`
  - `message_id`, `user_id`, `username`, `first_name`
  - `text` content
  - `timestamp` (UTC)
  - `has_media` flag, `media_type` (photo, video, document, etc.)
  - extracted `links` (regex/`urlextract`)
- Store all messages in a `messages` table; never delete (or rotate after N days, see config).

### 2. Media & Link Storage on Yandex Disk

- For each message containing an **image** (photo or image-document):
  - Download the file via Telegram Bot API.
  - Upload to Yandex Disk path: `/TelegramBot/{ChatName_sanitized}/{YYYY-MM-DD}/images/{message_id}_{original_filename}`
- For each **link** found in messages:
  - Append to a daily text file: `/TelegramBot/{ChatName_sanitized}/{YYYY-MM-DD}/links.txt`
  - Format per line: `[HH:MM] @username: <url> — <surrounding context>`
- Yandex Disk OAuth token stored in `.env`.
- Implement **retry logic** (3 attempts with exponential backoff) for upload failures.
- If upload fails permanently, log the error and keep the file in a local `pending/` directory for the next run.

### 3. Daily Summary Generation

- Run **once a day at a fixed time** (default `09:00`, configurable via `SUMMARY_TIME` env var, server timezone).
- For each chat the bot tracks:
  1. Fetch all messages from the **previous 24 hours** (configurable window).
  2. Format them into a single prompt for Gemini.
  3. Call Gemini API with a system prompt (in Russian) asking it to:
     - Identify **main discussion themes** (3–7 typical).
     - For each theme: write 2–4 sentence summary, list key participants, note any decisions/conclusions reached.
     - Format output as Markdown with theme headers (`## Тема: ...`).
     - Keep the whole summary under ~3000 characters (Telegram message limit is 4096).
  4. Cache the generated summary in a `summaries` SQLite table (one row per chat per day).

**Gemini prompt template (in Russian):**
```
Ты — ассистент, который анализирует переписку в Telegram-чате и составляет краткое резюме за день.

Чат: {chat_title}
Дата: {date}
Количество сообщений: {count}

Сообщения:
{formatted_messages}

Задача:
1. Выдели 3–7 основных тем обсуждения.
2. Для каждой темы напиши краткое резюме (2–4 предложения).
3. Укажи ключевых участников обсуждения.
4. Отметь принятые решения или важные выводы, если они есть.
5. Используй Markdown: каждая тема — заголовок "## Тема: <название>".
6. Общая длина — до 3000 символов.
7. Пиши на русском языке.
```

### 4. Subscription Management (Bot Commands)

The bot must support the following commands in **direct messages**:

| Command | Behavior |
|---|---|
| `/start` | Welcome message (in Russian), brief instructions. |
| `/subscribe <chat_id>` | Subscribe the user to daily summaries from a specific chat. The user must be a member of that chat (verify via `getChatMember`). |
| `/unsubscribe <chat_id>` | Cancel subscription. |
| `/list` | List all subscriptions of the user. |
| `/chats` | List all chats the bot is currently active in (so the user knows the IDs). |
| `/help` | Show all commands. |

**Group-chat commands** (in the chat itself, requires admin to invoke):

| Command | Behavior |
|---|---|
| `/enable_summary` | Toggle whether the daily summary is **also posted in the group itself** (not only DMed to subscribers). Saved in DB per chat. |
| `/disable_summary` | Disable in-group posting. |
| `/status` | Show bot status: messages collected today, last summary time, in-group posting on/off. |

### 5. Daily Delivery

At `SUMMARY_TIME` every day:
1. For every chat in the database:
   - Generate summary (see §3).
   - For every user subscribed to that chat → **send via DM**.
   - If the chat has in-group posting enabled → **also post in the group**.
2. If a DM fails (user blocked the bot), mark the subscription as `inactive` and log it.

---

## Database Schema (SQLite)

```sql
CREATE TABLE chats (
    chat_id INTEGER PRIMARY KEY,
    chat_title TEXT,
    chat_type TEXT,
    in_group_post BOOLEAN DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    message_id INTEGER,
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    text TEXT,
    has_media BOOLEAN DEFAULT 0,
    media_type TEXT,
    links TEXT,  -- JSON array
    timestamp TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
);

CREATE INDEX idx_messages_chat_time ON messages(chat_id, timestamp);

CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    chat_id INTEGER,
    active BOOLEAN DEFAULT 1,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, chat_id)
);

CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    summary_date DATE,
    content TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, summary_date)
);

CREATE TABLE upload_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_path TEXT,
    remote_path TEXT,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Project Structure

```
telegram-summary-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py                 # Entry point, sets up Application + scheduler
│   ├── config.py               # Loads .env, validates required vars
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── messages.py         # MessageHandler — saves all incoming messages
│   │   ├── commands.py         # CommandHandlers (/start, /subscribe, etc.)
│   │   └── admin.py            # Group-admin commands
│   ├── services/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLite async wrapper
│   │   ├── gemini.py           # Google Gemini API client
│   │   ├── yandex_disk.py      # Yandex Disk upload helpers
│   │   ├── summarizer.py       # Builds prompt, calls Gemini, stores result
│   │   └── scheduler.py        # APScheduler setup, daily job
│   └── utils/
│       ├── __init__.py
│       ├── link_extractor.py
│       └── text_formatter.py
├── data/                       # SQLite DB (volume-mounted)
├── logs/
├── pending/                    # Files queued for re-upload
├── tests/
│   ├── test_summarizer.py
│   ├── test_database.py
│   └── test_yandex_disk.py
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Environment Variables (`.env.example`)

```env
# Telegram
TELEGRAM_BOT_TOKEN=

# Google Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash

# Yandex Disk
YANDEX_DISK_TOKEN=
YANDEX_DISK_ROOT=/TelegramBot

# Schedule
SUMMARY_TIME=09:00
TIMEZONE=Europe/Moscow
SUMMARY_WINDOW_HOURS=24

# Database
DATABASE_PATH=/app/data/bot.db

# Logging
LOG_LEVEL=INFO
LOG_PATH=/app/logs/bot.log

# Retention (days; 0 = forever)
MESSAGE_RETENTION_DAYS=30
```

---

## Docker Setup

**`Dockerfile`:**
- Base: `python:3.11-slim`
- Install deps from `requirements.txt`
- Non-root user
- Volume mounts for `data/`, `logs/`, `pending/`

**`docker-compose.yml`:**
- One service: `bot`
- Restart policy: `unless-stopped`
- Mount volumes: `./data`, `./logs`, `./pending`
- Read `.env` automatically
- Healthcheck: pings DB connection

---

## Implementation Notes

1. **Async everywhere** — `python-telegram-bot` v21+ is fully async; pair with `aiosqlite` and `httpx`/`aiohttp` for Yandex Disk.
2. **Privacy mode** — README must explain how to disable bot privacy mode via @BotFather (`/setprivacy` → Disable) so the bot can read all group messages, not just commands.
3. **Rate limits**:
   - Gemini free tier: ~15 RPM for `gemini-1.5-flash` — fine for daily batch.
   - Yandex Disk: respect 429 responses, back off.
4. **Message chunking** — if a single chat's daily messages exceed Gemini's input limit (1M tokens is huge, but be defensive), chunk and run map-reduce summarization.
5. **Long summaries** — if generated summary exceeds 4096 chars, split into multiple Telegram messages.
6. **Privacy** — README must mention that members of the chat should be informed the bot is logging messages (GDPR/legal note).
7. **Error handling** — wrap every external call (Telegram, Gemini, Yandex) in try/except with logging; never let one failed chat block others.
8. **Testing** — at minimum, unit tests for: link extraction, summary prompt building, DB CRUD, Yandex Disk path generation. Mock external APIs.

---

## README must include

- Step-by-step setup:
  1. Create bot via @BotFather, copy token.
  2. Disable privacy mode via @BotFather.
  3. Get Gemini API key from https://aistudio.google.com/.
  4. Get Yandex Disk OAuth token (link to https://yandex.com/dev/disk/poligon/).
  5. Fill `.env`.
  6. `docker-compose up -d`.
  7. Add bot to a group, promote to admin.
  8. Open DM with the bot, send `/start`, then `/subscribe <chat_id>`.
- How to find a chat's `chat_id` (use `/chats` command after the bot is added).
- Troubleshooting section.
- Privacy/legal disclaimer.

---

## Acceptance Criteria

- [ ] Bot saves every message from every chat it's in to SQLite.
- [ ] Images are uploaded to Yandex Disk under `/TelegramBot/{ChatName}/{YYYY-MM-DD}/images/`.
- [ ] Links are appended to daily `links.txt` on Yandex Disk.
- [ ] At the configured time, every subscriber receives a Russian Markdown summary in DM, grouped by themes.
- [ ] Group admins can toggle in-group posting via `/enable_summary` / `/disable_summary`.
- [ ] All commands listed above work and respond in Russian.
- [ ] Project runs cleanly with `docker-compose up`.
- [ ] All secrets are in `.env`; nothing hardcoded.
- [ ] Logs are written to `logs/bot.log`.
- [ ] Crashes/restarts do not lose messages or duplicate summaries.

---

## Out of Scope (for v1)

- Reading historical messages from before the bot was added (Telegram bots can't do this).
- Voice/video transcription.
- Web dashboard.
- Multi-language summaries (Russian only for now).
- User-level configuration of summary time (one global time).
