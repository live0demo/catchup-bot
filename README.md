# Catchup Bot

A small, single-process Telegram bot that:

- summarizes group chat **catch-ups** since a checkpoint you set
- creates **one-time and recurring reminders**
- runs on long polling, with **SQLite** as the only datastore
- works **without any paid API** (local extractive summarizer); optionally upgrades to an OpenAI-compatible LLM via env var

Built to be deployable in ~5 minutes on a small VPS, Render, Railway, or any Docker host.

---

## Telegram limitations you must know

1. **Bots cannot read your real "unread" state.** Telegram exposes no such API. We don't fake it. Instead, you set a **checkpoint** with `/markread`, and `/catchup` summarizes everything the bot saw in that chat after that checkpoint.
2. **Group message visibility depends on Privacy Mode.** By default a Telegram bot only sees commands and replies to itself in groups. To let it see all messages (and thus enable real catch-up summaries):
   - Open BotFather → `/mybots` → pick your bot → **Bot Settings** → **Group Privacy** → **Disable**.
   - Add the bot to the group. Re-add it if it was already there before disabling privacy.
3. **Bots cannot fetch historical messages.** The cache only contains messages the bot witnessed while running.
4. **Bot identity (display name, @username, profile bio, profile picture) is owned by Telegram via BotFather.** This app's `BOT_DISPLAY_NAME`, `BOT_USERNAME_HINT`, `BOT_SHORT_DESCRIPTION`, and `BOT_BRAND_EMOJI` only control in-app text in `/start`, `/help`, and logs.

---

## Commands

| Command | What it does |
|---|---|
| `/start` | Welcome + quick reference |
| `/help` | Full help including limitations |
| `/tutorials` | Worked, copy-pasteable examples for every feature |
| `/markread` | Set checkpoint here for you in this chat (manual) |
| `/catchup` | Summarize messages since your checkpoint (medium) |
| `/catchup_short` | Compact summary |
| `/catchup_detailed` | Full chronological digest + sections |
| `/autosummary on\|off` | Save daily-digest preference (MVP: stored, manual trigger via `/catchup`) |
| `/remind <when> <text>` | Create a reminder. See examples below. |
| `/list_reminders` | List your active reminders |
| `/delete_reminder <id>` | Cancel a reminder |
| `/set_timezone <IANA>` | e.g. `Europe/Berlin`, `America/Los_Angeles` |
| `/ask <question>` | Free-form Q&A backed by the configured LLM (requires `LLM_API_KEY`) |

> **Auto-checkpoint:** when you send any non-command message in a group,
> your checkpoint for that group is automatically advanced to that message.
> So `/catchup` for active members shows "everything since I last spoke."
> Lurkers who never type still need `/markread`.

### Reminder syntax

```
/remind in 30 minutes water plants
/remind tomorrow 9am submit report
/remind today 18:00 call mom
/remind monday 8:00 deploy
/remind on 2026-04-20 09:00 doctor
/remind every monday 8:00 team sync
/remind every day 9:00 take vitamins
/remind every 2 hours stand up
```

If the time of day is missing (e.g. `/remind tomorrow buy bread`), the bot defaults to **09:00 in your timezone** and asks you to confirm with inline buttons.

---

## Optional: enable the AI (free providers, no card required)

The bot ships with a built-in extractive summarizer that always works. To
upgrade to an LLM (better summaries + the `/ask` command), set three env
vars. Pick **one** provider:

### Google Gemini (recommended for Vietnamese)
1. Open https://aistudio.google.com/apikey → **Create API key** (uses your Google account, no card).
2. Set in `.env` / Replit Secrets:
   ```
   LLM_API_KEY=<paste key>
   LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
   LLM_MODEL=gemini-2.0-flash
   SUMMARY_LANGUAGE=Vietnamese
   ```
   Free quota: 1500 req/day, 15 req/min. More than enough for a personal bot.

### Groq (very fast, generous quota)
1. Open https://console.groq.com/keys → sign up (no card) → **Create API Key**.
2. Set:
   ```
   LLM_API_KEY=<paste key>
   LLM_BASE_URL=https://api.groq.com/openai/v1
   LLM_MODEL=llama-3.3-70b-versatile
   SUMMARY_LANGUAGE=Vietnamese
   ```
   Free quota: 14,400 req/day.

### OpenRouter (mix of free models)
1. Open https://openrouter.ai/keys → sign up → create key.
2. Set:
   ```
   LLM_API_KEY=<paste key>
   LLM_BASE_URL=https://openrouter.ai/api/v1
   LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
   SUMMARY_LANGUAGE=Vietnamese
   ```

After updating Secrets/`.env`, restart the bot. `/catchup` summaries and
`/ask` answers will use the LLM. If the LLM call fails (quota / network /
bad key), summaries fall back to the local extractive summarizer.

---

## Renaming / branding the bot

Two layers control how your bot appears:

| Where | Controlled by | What it sets |
|---|---|---|
| Telegram itself | **BotFather** | Display name, `@username`, profile photo, bio, command list, group privacy |
| This app | `.env` | In-app text in `/start`, `/help`, log lines |

**To rename the bot in BotFather:**

1. Open a chat with [@BotFather](https://t.me/BotFather), send `/mybots`.
2. Pick your bot → **Edit Bot** → **Edit Name** (display name) or use **Edit About** / **Edit Description** for the profile bio.
3. The `@username` is set when you create the bot via `/newbot`. It can only be changed by deleting and re-creating the bot.
4. Optional but recommended: BotFather → **Bot Settings** → **Edit Commands** to register the slash-command list shown in the Telegram UI.

**To re-brand in the app:**

Edit `.env`:

```
BOT_DISPLAY_NAME=Owl Briefer
BOT_USERNAME_HINT=@owl_briefer_bot
BOT_SHORT_DESCRIPTION=Your group catch-up assistant.
BOT_BRAND_EMOJI=🦉
```

Then restart the bot.

---

## Local run

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows (Git Bash)
source .venv/Scripts/activate

pip install -r requirements.txt
cp .env.example .env       # Windows: copy .env.example .env
# edit .env and put your BOT_TOKEN in
python main.py
```

Run tests:

```bash
pytest
```

---

## Docker

```bash
cp .env.example .env
# edit .env
docker compose up --build
```

The SQLite DB is persisted to `./data/bot.db` via the `./data:/app/data` volume.

---

## Deploy: VPS

```bash
# On the VPS (Ubuntu/Debian example)
sudo apt update && sudo apt install -y python3.11 python3.11-venv git
git clone <your-repo-url> catchup-bot && cd catchup-bot
cp .env.example .env && nano .env       # set BOT_TOKEN and branding
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data

# Quick way: tmux/screen
tmux new -s bot
python main.py
# Ctrl+B then D to detach.

# Better way: systemd unit
sudo tee /etc/systemd/system/catchup-bot.service >/dev/null <<'EOF'
[Unit]
Description=Catchup Bot
After=network.target

[Service]
WorkingDirectory=/home/ubuntu/catchup-bot
EnvironmentFile=/home/ubuntu/catchup-bot/.env
ExecStart=/home/ubuntu/catchup-bot/.venv/bin/python main.py
Restart=always
RestartSec=5
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now catchup-bot
sudo journalctl -u catchup-bot -f
```

---

## Deploy: Render

1. Push this repo to GitHub.
2. On Render, create a new **Background Worker**.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python main.py`
5. Add env vars from `.env.example` (at minimum `BOT_TOKEN`).
6. Add a **Persistent Disk** mounted at `/app/data` (1 GB is plenty).
7. Set `DATABASE_URL=sqlite:////app/data/bot.db` (note 4 slashes for absolute path).

> Free-tier note: Render free workers can be put to sleep. For a reminder bot, prefer the cheapest paid worker so APScheduler keeps running.

---

## Deploy: Railway

1. Push this repo to GitHub and **Deploy from Repo** on Railway.
2. Railway auto-detects the `Dockerfile`. (You can also let it use the `Procfile`.)
3. Add env vars from `.env.example`.
4. Add a **Volume** mounted at `/app/data`. Set `DATABASE_URL=sqlite:////app/data/bot.db`.
5. Deploy. That's it.

---

## Architecture (one paragraph)

A single Python 3.11 process. **aiogram 3** runs the Telegram long-polling loop; **APScheduler `AsyncIOScheduler`** runs reminder jobs in the same event loop, so there is no separate worker. Reminders persist in SQLite and are re-loaded on startup; missed firings during downtime are scheduled to fire shortly after restart. Each reminder firing is idempotent thanks to a unique `(reminder_id, fire_time)` row in `reminder_deliveries`. Group messages are cached in `messages_cache` (subject to Telegram Privacy Mode) and trimmed by a periodic cleanup job. Summarization is delegated to `app.services.llm.summarize`, which uses a built-in extractive summarizer by default and an OpenAI-compatible HTTP API when `LLM_API_KEY` is set; LLM failures transparently fall back to the local one.

---

## License

MIT — do whatever, no warranty.
