# ⏱️ WORLD TIMER - 2026 CALENDAR

A Telegram bot that posts scheduled market reminders and special events to your channel.

---

## 📋 TABLE OF CONTENTS

- [NORMAL DAY](#-normal-day)
- [HOLIDAYS](#-holidays)
- [SPECIAL DAYS](#-special-days)
- [WEEKEND EVENTS](#-weekend-events)
- [UNIVERSAL EVENTS](#-universal-events)
- [CUSTOM EVENTS](#-custom-events)
- [ASTERISK LEGEND](#-asterisk-legend)
- [CONFIGURATION](#-configuration)

---

## 📅 NORMAL DAY

*Applies: Mon 00:00 - Fri 15:00 + Sun 15:00 - Sun 24:00 (GMT-7)*

| Time | Event | Type |
|------|-------|------|
| 00:30 | ⏰ London Open | Advance (30 min) |
| 01:00 | 🇬🇧 London Open | Session Open |
| 01:45 | ⏰ Asia-Europe Overlap | Advance (15 min) |
| 02:00 | 🌏 Asia-Europe Overlap | Overlap Event |
| 07:15 | ⏰ New York Open | Advance (15 min) |
| 07:30 | 🗽 New York Open / Overlap starts | Session Open |
| 08:00 | 📅 [day of week] Market | Weekly Marker |
| 08:45 | ⚡ Overlap peak | Peak Activity |
| 09:30 | ⏰ London Close | Advance (30 min) |
| 10:00 | 🏁 London Close | Session Close |
| 13:00 | ⏰ New York Close | Advance (1 hour) |
| 14:00 | 🏁 New York Close | Session Close |
| 15:00 | 🔄 Forex Rollover | Daily Reset |
| 17:00 | ⏰ Tokyo Open | Advance (1 hour) |
| 18:00 | 🇯🇵 Tokyo Open | Session Open |

---

## 🟥 HOLIDAYS

*Only these messages. NORMAL DAY does NOT apply on these dates.*

| Date | Time | Event |
|------|------|-------|
| 01 Jan | 08:00 | 🎉 New Year's Day (Wall Street CLOSED) |
| 19 Jan | 08:00 | 🕊️ Martin Luther King Jr. Day (Wall Street CLOSED) |
| 16 Feb | 08:00 | 🇺🇸 Presidents' Day (Wall Street CLOSED) |
| 03 Apr | 08:00 | ✝️ Good Friday (Wall Street CLOSED) |
| 25 May | 08:00 | 🎖️ Memorial Day (Wall Street CLOSED) |
| 19 Jun | 08:00 | ✊🏿 Juneteenth (Wall Street CLOSED) |
| 03 Jul | 08:00 | 🎆 Independence Day (observed) (Wall Street CLOSED) |
| 07 Sep | 08:00 | 👷 Labor Day (Wall Street CLOSED) |
| 26 Nov | 08:00 | 🦃 Thanksgiving (Wall Street CLOSED) |
| 25 Dec | 08:00 | 🎄 Christmas Day (Wall Street CLOSED) |
| 27 Nov | 08:00 | 🛍️ Black Friday * (early close 13:00) |
| 24 Dec | 08:00 | 🎄 Christmas Eve * (early close 13:00) |

---

## 🌟 SPECIAL DAYS

*These messages are ADDED to NORMAL DAY (or HOLIDAYS if applicable).*

| Date | Time | Event |
|------|------|-------|
| 01 Jan | 09:00 | 📆 Q1 starts - High Activity (Jan-Mar) |
| 02 Feb | 08:00 | 🕯️ Imbolc (Candlemas) |
| 14 Feb | 08:00 | 💘 Valentine's Day |
| 17 Mar | 08:00 | ☘️ St. Patrick's Day |
| 20 Mar | 08:00 | 🌸 Spring Equinox (Ostara) |
| 01 Apr | 09:00 | 📆 Q2 starts - Normal Activity (Apr-Jun) |
| 01 May | 08:00 | 🔥 Beltane |
| 21 Jun | 08:00 | ☀️ Summer Solstice (Litha) |
| 01 Aug | 08:00 | 🌾 Lammas / Lughnasadh |
| 01 Aug | 09:00 | 📆 August - Slow Market (summer lull) |
| 23 Sep | 08:00 | 🍂 Autumn Equinox (Mabon) |
| 01 Sep | 09:00 | 📆 Q4 starts - High Activity (Sep-Nov) |
| 30 Oct | 08:00 | 💀 Samhain |
| 31 Oct | 08:00 | 🎃 Halloween |
| 21 Dec | 08:00 | ❄️ Winter Solstice (Yule) |
| 01 Dec | 09:00 | 📆 December - Low Liquidity |
| 31 Dec | 08:00 | 🎆 New Year's Eve |

---

## ⏰ WEEKEND EVENTS

*Special messages for market open/close cycles.*

| Day | Time | Event |
|-----|------|-------|
| Friday | 14:00 | ⏰ Markets close in 1 hour * |
| Friday | 15:00 | 🔒 WEEKLY MARKET CLOSE * |
| Saturday | 00:01 | 🚫 All markets closed * |
| Sunday | 00:01 | 🚫 All markets closed * |
| Sunday | 14:00 | ⏰ Markets open in 1 hour * |
| Sunday | 15:00 | 🔓 WEEKLY MARKET OPEN * |

---

## 🌍 UNIVERSAL EVENTS

*Events that happen every day regardless of market conditions.*

| Time | Event |
|------|-------|
| 00:00 | 🌍 New UTC Day Begins |

---

## 📝 CUSTOM EVENTS

*Personal reminders you can add anytime.*

| Date | Time | Event |
|------|------|-------|
| 12 Apr 2026 | 17:00 | 🦷 Dentist appointment |

*(Add your own in the `custom` section of events.json)*

---

## ⭐ ASTERISK LEGEND

| Asterisk | Meaning |
|----------|---------|
| `*` | Day/time with special condition (weekend rule or early close) |

---

## ⚙️ CONFIGURATION

### Environment Variables (.env)

```env
API_ID=12345
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
CHANNEL_ID=@your_channel
CHECK_INTERVAL=60
TIMEZONE=America/Mazatlan