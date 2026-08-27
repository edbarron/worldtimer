# ⏱️ WorldTimer – Energy Thermometer Bot

A Telegram bot that posts scheduled market reminders, holiday alerts, and liquidity‑level updates to your channel.  
It displays visual energy bars (1–10) for intraday liquidity, weekdays, and months.

---

## 📡 How to Use It?

There are **two ways**:

### Option 1 (recommended for end users)
**Follow the public Telegram channel:**  
👉 [@WorldTimer_WW](https://t.me/WorldTimer_WW)  

You'll automatically receive all scheduled messages (market opens/closes, holidays, liquidity peaks, etc.) without installing anything. **It's free and requires no configuration.**

### Option 2 (for developers)
Clone this repository if you want to:
- Customise events (add your own reminders).
- Modify the code or liquidity logic.
- Host your own instance of the bot.

Follow the installation instructions below.

---

## ✨ Features

- **Real‑time Liquidity Wave** – 30‑minute granularity based on Sydney, Tokyo, London, and New York sessions.
- **Energy Bars** – Visual `█░` bars for current liquidity, day of week, and month.
- **Holiday & Special Day Support** – Automatically disables normal day events on holidays.
- **Anti‑Spam** – Prevents duplicate messages within a configurable window.
- **Configurable Timezone** – Set via `events.json` or environment variable.
- **Daily Summary** – Posts a comprehensive market overview at cycle start.
- **Custom Events** – Add your own reminders in `events.json`.

---

## 🛠️ Tech Stack

- Python 3.10+
- Telethon (Telegram client)
- python-dotenv
- ZoneInfo (timezone handling)
- JSON for event storage

---

## 📦 Installation (only for self‑hosting)

1. **Clone the repository**
   ```bash
   git clone https://github.com/edbarron/worldtimer.git
   cd worldtimer
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**  
   Create a `.env` file in the root directory:
   ```env
   API_ID=your_telegram_api_id
   API_HASH=your_telegram_api_hash
   BOT_TOKEN=your_bot_token
   CHANNEL_ID=@your_channel
   CHECK_INTERVAL=60
   TIMEZONE=America/Mazatlan
   EVENTS_FILE=events.json
   ```

5. **Prepare the events file**  
   Place your `events.json` in the root (you can use the example provided in the repo).

6. **Run the bot**
   ```bash
   python worldtimer.py
   ```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description |
| :--- | :--- |
| `API_ID` | Your Telegram API ID (from my.telegram.org) |
| `API_HASH` | Your Telegram API hash |
| `BOT_TOKEN` | Bot token from BotFather |
| `CHANNEL_ID` | Channel username (e.g., `@mychannel`) or numeric ID |
| `CHECK_INTERVAL` | Seconds between checks (default 60) |
| `TIMEZONE` | IANA timezone (default `America/Mazatlan`) |
| `EVENTS_FILE` | Path to events JSON (default `events.json`) |

### events.json Structure

The bot reads all events from this file. It includes:

- `config` – timezone and anti_spam_minutes
- `holidays` – dates with full market closure
- `weekly` – day‑of‑week repeating events (e.g., Monday market markers)
- `weekend` – special weekend messages
- `universal` – daily events (e.g., UTC day start)
- `sessions` – market session open/close events (with advance warnings)
- `session_events` – overlap peaks, rollovers, etc.
- `special` – one‑off dates (equinoxes, holidays, etc.)
- `custom` – user‑defined personal reminders

A full reference is available in `calendar.md`.

---

## 📊 How It Works

### Liquidity Wave (WAVE_LVLS)

The bot uses a **48‑slot table** (30‑minute intervals starting at 15:00 local time) calibrated to the actual session hours:

- **Sydney** 15:00–24:00  
- **Tokyo** 16:00–01:00  
- **London** 00:00–09:00  
- **New York** 05:00–14:00  

The level (1–10) reflects how many sessions are open at that moment, with the **London+NY overlap (06:00–07:30 local)** as the 10/10 peak and the **14:00–15:00 dead zone** as the 1/10 floor.

### Energy Bars

- **Intraday** – derived from `WAVE_LVLS` and displayed as `███░░░░░░░` with a trend indicator (RISING/FALLING/STABLE).
- **Weekly** – based on the day of week (Monday 7 → Friday 1, etc.)
- **Monthly** – based on the month (e.g., October 10, March 10, December 1)

### Anti‑Spam

Each event has a unique ID. The bot will not send the same event again within the configured `anti_spam_minutes` (default 5).

### Daily Summary

At the start of each trading cycle (15:00 local time), the bot posts a summary containing:
- Current season
- Market status (crypto, forex, stocks)
- Weekly and monthly energy bars
- Today’s liquidity cycle timeline

---

## 📁 File Structure

```
worldtimer/
├── worldtimer.py          # Main bot code
├── events.json            # All event definitions
├── .env                   # Environment variables (not tracked)
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── calendar.md            # Reference calendar (human‑readable)
```

---

## 🧪 Testing

Run the bot in a test channel first. Ensure your `events.json` is correctly formatted. Use the `CHECK_INTERVAL` to speed up testing (e.g., set to 10 seconds).

---

## 📄 License

MIT – free to use, modify, and distribute.

---

**Maintainer:** [PxlCode Studio](https://pxlcode.xyz) · [GitHub](https://github.com/edbarron)
