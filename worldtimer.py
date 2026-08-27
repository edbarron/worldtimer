#!/usr/bin/env python3
"""
WorldTimer v6 - Energy Thermometer
Telegram bot that posts scheduled reminders with energy levels.

v6 change: WAVE_LVLS recalibrated to match the actual session hours
(Sydney 15:00-24:00, Tokyo 16:00-01:00, London 00:00-09:00,
New York 05:00-14:00, all local GMT-7 / America/Mazatlan), derived from
a real forex-hours reference and cross-checked against its stated
overlaps (London&NYSE 12:00-16:00 GMT, Tokyo&London 07:00-08:00 GMT,
Sydney&Tokyo 23:00-07:00 GMT). The level for each half-hour slot reflects
how many sessions are open at that moment, weighted so the London/NY
overlap (06:00-07:30 local) is the true 10/10 peak of the day and the
09:00-hour gap after NY closes (14:00-15:00 local, before Sydney reopens)
is the true 1/10 floor.

Carried over from v5:
- Single source of truth for liquidity levels (WAVE_LVLS), no separate
  static table that can drift out of sync with it.
- config-driven timezone / anti_spam_minutes (read from events.json).
- No duplicate is_holiday_today / get_today_holiday functions.
- weekly (day-of-week) messages use _weekly_energy() properly.
- _check_time uses a (last_loop, now] window so a slow tick can't
  silently drop a scheduled event.
"""

import os
import re
import json
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

# -----------------------------
# ENV CONFIG
# -----------------------------
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
TIMEZONE_ENV_DEFAULT = os.getenv("TIMEZONE", "America/Mazatlan")
EVENTS_FILE = os.getenv("EVENTS_FILE", "events.json")

SIGNATURE = "\n\n#WorldTimer @WorldTimer_WW"

# Categories where a liquidity LVL bar doesn't make sense to show, because
# the message is about weekly rhythm or non-market astro dates, not the
# intraday forex liquidity wave.
NO_WAVE_CATEGORIES = {"weekend", "special"}


class WorldTimer:
    def __init__(self):
        self.client = TelegramClient("worldtimer", API_ID, API_HASH)
        self.data = {}
        self.last_sent = {}
        self.last_summary_date = None
        self.tz = ZoneInfo(TIMEZONE_ENV_DEFAULT)
        self.anti_spam_seconds = 300
        self.running = False
        self.last_loop_time = None

    def load_events(self, filepath=None):
        if filepath is None:
            filepath = EVENTS_FILE
        path = Path(filepath)
        if not path.exists():
            print(f"❌ {filepath} not found")
            return False
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        print(f"✅ Calendar loaded from {filepath}")

        # config block: timezone + anti_spam_minutes actually take effect now
        cfg = self.data.get("config", {})
        tz_name = cfg.get("timezone", TIMEZONE_ENV_DEFAULT)
        try:
            self.tz = ZoneInfo(tz_name)
        except Exception as e:
            print(f"⚠️ Invalid timezone '{tz_name}' in config, keeping {TIMEZONE_ENV_DEFAULT}: {e}")
        self.anti_spam_seconds = int(cfg.get("anti_spam_minutes", 5)) * 60

        # Sanity check on the liquidity wave table
        if len(self.WAVE_LVLS) != 48:
            print(f"⚠️ WAVE_LVLS has {len(self.WAVE_LVLS)} entries, expected 48")

        return True

    # -----------------------------
    # ENERGY SCALES
    # -----------------------------
    def _weekly_energy(self, weekday):
        levels = {0: 7, 1: 8, 2: 10, 3: 8, 4: 8, 5: 1, 6: 2}
        return levels.get(weekday, 0)

    def _monthly_energy(self, month):
        levels = {
            1: 8, 2: 9, 3: 10, 4: 4, 5: 4, 6: 4,
            7: 5, 8: 2, 9: 6, 10: 10, 11: 10, 12: 1
        }
        return levels.get(month, 0)

    def _energy_bar(self, level):
        if level > 10:
            level = 10
        filled = "█" * min(level, 10)
        empty = "░" * (10 - min(level, 10))
        return filled + empty

    def _get_season_display(self, date):
        month, day = date.month, date.day
        if (month == 3 and day >= 21) or (4 <= month <= 5) or (month == 6 and day <= 20):
            return "🌹 Spring 🌹"
        elif (month == 6 and day >= 21) or (7 <= month <= 8) or (month == 9 and day <= 20):
            return "☀️ Summer"
        elif (month == 9 and day >= 21) or (10 <= month <= 11) or (month == 12 and day <= 20):
            return "🍂 Fall"
        else:
            return "☃️ Winter"

    # -----------------------------
    # LIQUIDITY WAVE (HORIZONTAL BAR)
    # -----------------------------
    # Single source of truth for intraday liquidity. Every wave-tagged
    # message derives its level from this table at the moment it fires.
    #
    # Calibrated to these session windows (local GMT-7 / America/Mazatlan):
    #   Sydney   15:00 - 24:00
    #   Tokyo    16:00 - 01:00 (+1 day)
    #   London   00:00 - 09:00
    #   New York 05:00 - 14:00
    # Table starts at 15:00 (index 0) in 30-minute steps, 48 slots = 24h.
    WAVE_LVLS = [
        2,2,                              # 15:00,15:30            Sydney only
        3,3,4,4,5,5,5,5,6,6,6,6,7,7,7,7,  # 16:00-23:30            Sydney+Tokyo (ramp)
        7,7,                              # 00:00,00:30            Tokyo+London
        8,8,8,7,7,7,6,6,                  # 01:00-04:30            London only
        8,9,10,10,10,10,9,8,              # 05:00-08:30            London+NY (MAX PEAK 06:00-07:30)
        7,6,6,5,5,4,4,3,3,2,               # 09:00-13:30            New York only
        1,1,                              # 14:00,14:30            dead zone (nothing open)
    ]

    def _get_wave_index(self, dt):
        base = dt.replace(hour=15, minute=0, second=0, microsecond=0)
        if dt < base:
            base = base - timedelta(days=1)
        delta = dt - base
        minutes = delta.total_seconds() / 60
        idx = int(minutes // 30)
        return max(0, min(len(self.WAVE_LVLS) - 1, idx))

    def _wave_energy(self, now):
        """Current liquidity level (1-10) straight from WAVE_LVLS."""
        return self.WAVE_LVLS[self._get_wave_index(now)]

    def get_liquidity_status(self, now):
        """Return a horizontal progress bar with trend emoji."""
        idx = self._get_wave_index(now)
        current_lvl = self.WAVE_LVLS[idx]
        prev_lvl = self.WAVE_LVLS[idx - 1] if idx > 0 else current_lvl

        bar = self._energy_bar(current_lvl)

        if current_lvl == 10:
            trend_emoji = "🌟"
            trend_text = "MAX PEAK"
        elif current_lvl == 1:
            trend_emoji = "⚫"
            trend_text = "NADIR"
        elif current_lvl > prev_lvl:
            trend_emoji = "🟢"
            trend_text = "RISING"
        elif current_lvl < prev_lvl:
            trend_emoji = "🔴"
            trend_text = "FALLING"
        else:
            trend_emoji = "⚪"
            trend_text = "STABLE"

        return f"{trend_emoji} {bar} ({current_lvl}/10) – {trend_text}"

    # -----------------------------
    # HELPERS
    # -----------------------------
    def _check_time(self, time_str, window_start, window_end):
        """
        True if the scheduled time falls inside (window_start, window_end].
        Using a window instead of an exact minute match means a slow loop
        iteration (or one skipped tick) can't silently drop an event.
        """
        t = datetime.strptime(time_str.strip(), "%H:%M").time()
        for day_offset in (0, -1):
            candidate = window_end.replace(
                hour=t.hour, minute=t.minute, second=0, microsecond=0
            ) + timedelta(days=day_offset)
            if window_start < candidate <= window_end:
                return True
        return False

    def _anti_spam(self, event_id):
        last = self.last_sent.get(event_id)
        if not last:
            return True
        now = datetime.now(ZoneInfo("UTC"))
        if (now - last).total_seconds() < self.anti_spam_seconds:
            return False
        return True

    def _format_time_12h(self, time_str):
        if not time_str:
            return ""
        t = datetime.strptime(time_str.strip(), "%H:%M")
        formatted = t.strftime("%I:%M %p")
        # Strip a single leading zero only (12:00 AM must stay "12:00 AM")
        return re.sub(r"^0", "", formatted)

    def is_holiday_today(self, now):
        """Return today's holiday entry, if any."""
        today = now.strftime("%Y-%m-%d")
        for event in self.data.get("holidays", []):
            if event.get("date") == today:
                return event
        return None

    async def send_message(self, event_id, original_message, now, time_str=None,
                            event_data=None, category="generic"):
        if not self._anti_spam(event_id):
            return

        try:
            title_map = {
                "london_close": ("🛑 🇪🇺 Euro Close", "Energy slows down", ["🇺🇸 NY", "🇲🇽 CDMX"], "💱: USD/CAD, USD/MXN, XAU/USD"),
                "ny_close": ("🛑 🗽 New York Close", "U.S. session ends — liquidity drops", [], "💱: USD/JPY, AUD/USD, NZD/USD"),
                "london": ("🇪🇺 London Open", "Europe session starts", [], "💱: EUR/USD, GBP/USD, EUR/JPY"),
                "new_york": ("🗽 New York Open", "US session starts — London overlap begins", ["🇺🇸 NY", "🇬🇧 London"], "💱: EUR/USD, GBP/USD, USD/CAD, XAU/USD"),
                "forex_rollover": ("🟥 END OF UTC DAY", "Quiet period: swaps, adjustments, lowest liquidity.\n⌛ Restarts in 2 hours.", [], ""),
                "friday_close": ("🔒 WEEKLY MARKET CLOSE", "Until Sunday 14:00\n🌙 Weekend mode activated", [], ""),
            }

            # Determine the liquidity level, if this category shows one at all.
            level = None
            if category == "weekly":
                level = self._weekly_energy(now.weekday())
            elif category not in NO_WAVE_CATEGORIES:
                level = self._wave_energy(now)

            is_wave_event = bool(event_data and event_data.get("wave"))

            if event_id in title_map:
                title, desc, active_markets, pairs = title_map[event_id]
                message = f"{title}"
                if level is not None and not is_wave_event:
                    message += f"\n\nLVL: {self._energy_bar(level)} ({level}/10)"
                message += f"\n{desc}"
                if active_markets:
                    message += "\n🟢 " + " ".join(active_markets)
                if pairs:
                    message += f"\n{pairs}"
            else:
                message = original_message
                if level is not None and not is_wave_event and "LVL:" not in message:
                    message = f"{message}\n\nLVL: {self._energy_bar(level)} ({level}/10)"

            if time_str:
                time_12h = self._format_time_12h(time_str)
                message += f"\n\n⏰ {time_12h}"

            # Wave events get the richer trend line instead of a bare LVL bar,
            # so there is exactly one liquidity figure per message, never two.
            if is_wave_event:
                status = self.get_liquidity_status(now)
                message += f"\n\n📊 Liquidity: {status}"

            message += SIGNATURE

            await self.client.send_message(CHANNEL_ID, message)
            level_note = f"{level}/10" if level is not None else "n/a"
            print(f"📤 {event_id} (level {level_note})")
            self.last_sent[event_id] = datetime.now(ZoneInfo("UTC"))
        except Exception as e:
            print(f"❌ send failed {event_id}: {e}")

    # -----------------------------
    # DAILY SUMMARY
    # -----------------------------
    async def send_daily_summary(self, is_startup=False):
        now = datetime.now(self.tz)
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        month_names = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]

        if now.hour > 14 or (now.hour == 14 and now.minute >= 30):
            cycle_date = now + timedelta(days=1)
        else:
            cycle_date = now

        cycle_day = cycle_date.strftime("%Y-%m-%d")
        cycle_weekday = cycle_date.weekday()
        cycle_weekday_name = weekday_names[cycle_weekday]
        cycle_month = cycle_date.month
        cycle_month_name = month_names[cycle_month - 1]

        today_str = now.strftime("%Y-%m-%d")

        if is_startup:
            summary = f"❂ WORLD TIMER STARTED — 🗓️{cycle_weekday_name}, {cycle_day}\n\n"
        else:
            summary = f"❂ WORLD TIMER — 🗓️{cycle_weekday_name}, {cycle_day}\n\n"

        summary += f"> 🕐 {self.tz.key if hasattr(self.tz, 'key') else TIMEZONE_ENV_DEFAULT}\n\n"

        highlights = []
        season_display = self._get_season_display(cycle_date)
        highlights.append(season_display)
        for event in self.data.get("special", []):
            if event.get("date") == today_str:
                highlights.append(event["message"].split('\n')[0])
        holiday = self.is_holiday_today(now)
        if holiday:
            highlights.append(holiday['message'].split('\n')[0])

        if highlights:
            summary += "🌟 Highlights:\n"
            for h in highlights:
                summary += f"> {h}\n"
            summary += "\n"

        crypto_status = "> Crypto ₿ 24/7 🟢"
        forex_status = "> Forex $ 24/5 🟢"
        stocks_status = "> Markets: 🇦🇺 · 🇯🇵 · 🇬🇧 · 🇺🇸 "

        summary += "📊 Market Status:\n\n"
        summary += f"{crypto_status}\n{forex_status}\n{stocks_status}\n"

        weekly_energy = self._weekly_energy(cycle_weekday)
        weekly_bar = self._energy_bar(weekly_energy)
        monthly_energy = self._monthly_energy(cycle_month)
        monthly_bar = self._energy_bar(monthly_energy)

        summary += f"> LVL: {weekly_bar} — {cycle_weekday_name}"
        if weekly_energy == 10:
            summary += " PEAK🔥"
        summary += "\n"
        summary += f"> LVL: {monthly_bar} — {cycle_month_name}"
        if monthly_energy == 10:
            summary += " PEAK🔥"
        summary += "\n\n"

        if cycle_weekday in [5, 6]:
            summary += "🏦 Today's Liquidity Cycle:\n\n> All markets closed (except crypto)\n"
        else:
            summary += "🏦 Today's Liquidity Cycle:\n\n"
            cycle_events = [
                ("03:00 PM", "🌏 Sydney/NZX Open · Day starts 🏁", 2),
                ("04:00 PM", "🇯🇵 Tokyo & 🇦🇺 Sydney Overlap", 3),
                ("12:00 AM", "🇬🇧 London Open · 🇯🇵 Tokyo overlap", 7),
                ("01:00 AM", "🇯🇵 Tokyo Close", 8),
                ("05:00 AM", "🇺🇸 NY Open · 🇬🇧 London overlap begins", 8),
                ("06:00 AM", "⚡ MAX PEAK ⚡", 10),
                ("09:00 AM", "🇬🇧 London Close", 7),
                ("02:00 PM", "🇺🇸 NY Close / Day ends 🏁", 1),
            ]
            for time_str, desc, level in cycle_events:
                bar = self._energy_bar(level)
                summary += f"> {time_str}  {bar}  {desc}\n"

        summary += SIGNATURE
        await self.client.send_message(CHANNEL_ID, summary)
        print(f"📋 Summary sent for {cycle_day}")

    # -----------------------------
    # EVENT CHECKERS
    # -----------------------------
    def _is_normal_day_active(self, now):
        """
        NORMAL DAY applies Mon 00:00 - Fri 15:00 + Sun 15:00 - Sun 24:00 (local tz),
        and is fully suspended on HOLIDAYS dates.
        """
        if self.is_holiday_today(now):
            return False
        wd = now.weekday()
        if wd == 5:  # Saturday: never
            return False
        if wd == 6:  # Sunday: only from 15:00 onward
            return now.hour >= 15
        if wd == 4:  # Friday: only until 15:00
            return not (now.hour > 15 or (now.hour == 15 and now.minute > 0))
        return True  # Mon-Thu

    async def check_holidays(self, now, ws, we):
        holiday = self.is_holiday_today(now)
        if not holiday:
            return
        if self._check_time(holiday["time"], ws, we):
            await self.send_message(holiday["id"], holiday["message"], now,
                                     holiday["time"], event_data=None, category="holiday")

    async def check_universal(self, now, ws, we):
        for event in self.data.get("universal", []):
            if self._check_time(event["time"], ws, we):
                await self.send_message(event["id"], event["message"], now,
                                         event["time"], event_data=None, category="universal")

    async def check_custom(self, now, ws, we):
        today = now.strftime("%Y-%m-%d")
        for event in self.data.get("custom", []):
            if event.get("date") != today:
                continue
            if self._check_time(event["time"], ws, we):
                await self.send_message(event["id"], event["message"], now,
                                         event["time"], event_data=event, category="custom")

    async def check_special(self, now, ws, we):
        today = now.strftime("%Y-%m-%d")
        for event in self.data.get("special", []):
            if event.get("date") != today:
                continue
            if self._check_time(event["time"], ws, we):
                await self.send_message(event["id"], event["message"], now,
                                         event["time"], event_data=None, category="special")

    async def check_weekly(self, now, ws, we):
        if not self._is_normal_day_active(now):
            return
        weekday = now.weekday()
        for event in self.data.get("weekly", []):
            if event["weekday"] != weekday:
                continue
            if "date" in event and event["date"] != now.strftime("%Y-%m-%d"):
                continue
            if self._check_time(event["time"], ws, we):
                await self.send_message(event["id"], event["message"], now,
                                         event["time"], event_data=None, category="weekly")

    async def check_weekend(self, now, ws, we):
        for event in self.data.get("weekend", []):
            if event["weekday"] == now.weekday() and self._check_time(event["time"], ws, we):
                await self.send_message(event["id"], event["message"], now,
                                         event["time"], event_data=None, category="weekend")

    async def check_sessions(self, now, ws, we):
        if not self._is_normal_day_active(now):
            return
        for session in self.data.get("sessions", []):
            if self._check_time(session["open"], ws, we):
                await self.send_message(session["id"], session["message"], now,
                                         session["open"], event_data=session, category="session")

    async def check_session_events(self, now, ws, we):
        if not self._is_normal_day_active(now):
            return
        for event in self.data.get("session_events", []):
            if self._check_time(event["time"], ws, we):
                await self.send_message(event["id"], event["message"], now,
                                         event["time"], event_data=event, category="session_event")

    # -----------------------------
    # RUN LOOP
    # -----------------------------
    async def run(self):
        import signal

        if BOT_TOKEN:
            await self.client.start(bot_token=BOT_TOKEN)
        else:
            await self.client.start()

        print("✅ WorldTimer connected")
        self.running = True

        def stop_handler(*args):
            print("\n🛑 Shutdown signal received")
            self.running = False

        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGTERM, stop_handler)

        try:
            now = datetime.now(self.tz)
            now_date = now.strftime("%Y-%m-%d")
            now_time = self._format_time_12h(now.strftime("%H:%M"))
            await self.client.send_message(
                CHANNEL_ID,
                f"🤖 WorldTimer started\n📅 {now_date} {now_time}"
            )
        except Exception as e:
            print("⚠️ startup message failed:", e)

        try:
            now = datetime.now(self.tz)
            if now.hour > 14 or (now.hour == 14 and now.minute >= 30):
                current_cycle_date = (now + timedelta(days=1)).date()
            else:
                current_cycle_date = now.date()

            if self.last_summary_date != current_cycle_date:
                await self.send_daily_summary(is_startup=True)
                self.last_summary_date = current_cycle_date
            else:
                print("Startup summary already sent for this cycle")
        except Exception as e:
            print("⚠️ startup summary failed:", e)

        self.last_loop_time = datetime.now(self.tz) - timedelta(seconds=CHECK_INTERVAL)

        try:
            while self.running:
                now = datetime.now(self.tz)
                window_start, window_end = self.last_loop_time, now

                if now.hour == 14 and now.minute == 30 and self.last_summary_date != now.date():
                    await self.send_daily_summary(is_startup=False)
                    self.last_summary_date = now.date()

                await self.check_holidays(now, window_start, window_end)
                await self.check_weekend(now, window_start, window_end)
                await self.check_universal(now, window_start, window_end)
                await self.check_sessions(now, window_start, window_end)
                await self.check_session_events(now, window_start, window_end)
                await self.check_weekly(now, window_start, window_end)
                await self.check_special(now, window_start, window_end)
                await self.check_custom(now, window_start, window_end)

                self.last_loop_time = now
                await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"❌ Fatal error in main loop: {e}")
        finally:
            try:
                now = datetime.now(self.tz)
                now_date = now.strftime("%Y-%m-%d")
                now_time = self._format_time_12h(now.strftime("%H:%M"))
                await self.client.send_message(
                    CHANNEL_ID,
                    f"🛑 WorldTimer stopped\n📅 {now_date} {now_time}"
                )
            except Exception as e:
                print(f"⚠️ shutdown message failed: {e}")
            await self.client.disconnect()
            print("👋 Shutdown complete")


async def main():
    timer = WorldTimer()
    if not timer.load_events():
        return
    await timer.run()


if __name__ == "__main__":
    asyncio.run(main())