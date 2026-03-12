#!/usr/bin/env python3
"""
WorldTimer - Telegram bot that posts scheduled reminders to a channel
Version 2.0 - With Holiday/Special/Normal logic
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

# Load .env
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
TIMEZONE = os.getenv("TIMEZONE", "America/Mazatlan")

class WorldTimer:
    def __init__(self):
        self.client = TelegramClient('worldtimer', API_ID, API_HASH)
        self.events = []
        self.last_sent = {}  # track last send time per event
        
    def load_events(self, filepath="events.json"):
        """Load events from JSON file"""
        path = Path(filepath)
        if not path.exists():
            print(f"❌ events.json not found")
            return False
            
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.events = data.get("events", [])
        print(f"✅ Loaded {len(self.events)} events")
        return True
    
    def is_holiday_today(self, date: datetime) -> bool:
        """Check if today is a holiday (type: holiday)"""
        date_str = date.strftime("%Y-%m-%d")
        for event in self.events:
            if event.get("type") == "holiday" and event.get("date") == date_str:
                return True
        return False
    
    def get_holiday_event(self, date: datetime):
        """Get holiday event for today"""
        date_str = date.strftime("%Y-%m-%d")
        for event in self.events:
            if event.get("type") == "holiday" and event.get("date") == date_str:
                return event
        return None
    
    def get_special_events(self, date: datetime):
        """Get all special events for today"""
        date_str = date.strftime("%Y-%m-%d")
        specials = []
        for event in self.events:
            if event.get("type") == "special" and event.get("date") == date_str:
                specials.append(event)
        return specials
    
    def is_weekend_closed(self, now: datetime) -> bool:
        """Check if market is closed due to weekend"""
        # Saturday all day
        if now.weekday() == 5:  # Saturday
            return True
        # Sunday before 15:00
        if now.weekday() == 6 and now.hour < 15:  # Sunday before 3pm
            return True
        # Friday after 15:00
        if now.weekday() == 4 and now.hour >= 15:  # Friday after 3pm
            return True
        return False
    
    def should_send_normal(self, event: dict, now: datetime) -> bool:
        """Check if normal event should be sent"""
        # Don't send normal events on holidays
        if self.is_holiday_today(now):
            return False
        
        # Don't send normal events when market is closed (weekend)
        if self.is_weekend_closed(now):
            return False
        
        # Check early close condition
        if self.is_early_close_day(now):
            early_close_time = self.get_early_close_time(now)
            if now.time() >= datetime.strptime(early_close_time, "%H:%M").time():
                return False
        
        # Anti-spam
        last = self.last_sent.get(event["id"])
        if last and (now - last).total_seconds() < 300:
            return False
        
        # Check time
        event_time = datetime.strptime(event["time"], "%H:%M").time()
        if now.hour == event_time.hour and now.minute == event_time.minute:
            return True
        
        # Check advance
        if "advance" in event:
            event_dt = datetime.combine(now.date(), event_time)
            event_dt = event_dt.replace(tzinfo=now.tzinfo)
            advance_dt = event_dt - timedelta(minutes=event["advance"])
            if advance_dt.date() == now.date():
                if now.hour == advance_dt.hour and now.minute == advance_dt.minute:
                    return True
        
        return False
    
    def should_send_special(self, event: dict, now: datetime) -> bool:
        """Check if special event should be sent"""
        # Special events always send on their date, even on holidays/weekends
        if "date" in event:
            if event["date"] != now.strftime("%Y-%m-%d"):
                return False
        
        # Anti-spam
        last = self.last_sent.get(event["id"])
        if last and (now - last).total_seconds() < 300:
            return False
        
        # Check time
        event_time = datetime.strptime(event["time"], "%H:%M").time()
        return (now.hour == event_time.hour and now.minute == event_time.minute)
    
    def should_send_weekend_event(self, event: dict, now: datetime) -> bool:
        """Check if weekend event should be sent"""
        if event.get("condition") != "weekend":
            return False
        
        # Saturday event
        if event["id"] == "saturday_closed" and now.weekday() == 5:
            if now.hour == 0 and now.minute == 1:
                return True
        
        # Sunday closed event (before 15:00)
        if event["id"] == "sunday_closed" and now.weekday() == 6:
            if now.hour == 0 and now.minute == 1:
                return True
        
        # Sunday open advance (14:00)
        if event["id"] == "sunday_open_advance" and now.weekday() == 6:
            event_time = datetime.strptime(event["time"], "%H:%M").time()
            return (now.hour == event_time.hour and now.minute == event_time.minute)
        
        # Sunday open (15:00)
        if event["id"] == "sunday_open" and now.weekday() == 6:
            event_time = datetime.strptime(event["time"], "%H:%M").time()
            return (now.hour == event_time.hour and now.minute == event_time.minute)
        
        # Friday close advance (14:00)
        if event["id"] == "friday_close_advance" and now.weekday() == 4:
            event_time = datetime.strptime(event["time"], "%H:%M").time()
            return (now.hour == event_time.hour and now.minute == event_time.minute)
        
        # Friday close (15:00)
        if event["id"] == "friday_close" and now.weekday() == 4:
            event_time = datetime.strptime(event["time"], "%H:%M").time()
            return (now.hour == event_time.hour and now.minute == event_time.minute)
        
        return False
    
    def is_early_close_day(self, now: datetime) -> bool:
        """Check if today has early close"""
        date_str = now.strftime("%Y-%m-%d")
        for event in self.events:
            if event.get("condition") == "early_close" and event.get("date") == date_str:
                return True
        return False
    
    def get_early_close_time(self, now: datetime) -> str:
        """Get early close time for today"""
        date_str = now.strftime("%Y-%m-%d")
        for event in self.events:
            if event.get("condition") == "early_close" and event.get("date") == date_str:
                return event.get("close_time", "13:00")
        return "13:00"
    
    async def send_event(self, event: dict):
        """Send event message to channel"""
        try:
            now = datetime.now(ZoneInfo(TIMEZONE))
            
            # Build message based on event type
            if "advance" in event and self._is_advance(event, now):
                msg = self._build_advance_message(event)
            else:
                msg = event["message"]
            
            # Add time footer
            if not msg.endswith(f"⏰ {event['time']}"):
                msg += f"\n\n⏰ {event['time']}"
            
            # Send
            await self.client.send_message(CHANNEL_ID, msg)
            
            event_type = event.get("type", "unknown")
            print(f"📤 [{event_type.upper()}] {event['name']} sent")
            
            # Update last sent time
            self.last_sent[event["id"]] = datetime.now(ZoneInfo("UTC"))
            
        except Exception as e:
            print(f"❌ Failed to send {event['id']}: {e}")
    
    def _is_advance(self, event: dict, now: datetime) -> bool:
        """Check if this is an advance reminder"""
        if "advance" not in event:
            return False
        
        event_time = datetime.strptime(event["time"], "%H:%M").time()
        event_dt = datetime.combine(now.date(), event_time)
        event_dt = event_dt.replace(tzinfo=now.tzinfo)
        advance_dt = event_dt - timedelta(minutes=event["advance"])
        
        return (advance_dt.date() == now.date() and 
                now.hour == advance_dt.hour and 
                now.minute == advance_dt.minute)
    
    def _build_advance_message(self, event: dict) -> str:
        """Build message for advance reminder"""
        advance_minutes = event["advance"]
        if advance_minutes >= 60:
            hours = advance_minutes // 60
            time_text = f"{hours} hour{'s' if hours > 1 else ''}"
        else:
            time_text = f"{advance_minutes} minutes"
        
        return f"⏰ {time_text} until {event['name']}\n\n{event['message']}"
    
    async def run(self):
        """Main loop"""
        # Start client
        if BOT_TOKEN:
            await self.client.start(bot_token=BOT_TOKEN)
        else:
            await self.client.start()
        
        print(f"✅ WorldTimer connected")
        print(f"📢 Channel: {CHANNEL_ID}")
        print(f"⏱️  Check interval: {CHECK_INTERVAL}s")
        print(f"🌍 Timezone: {TIMEZONE}\n")
        
        # Send startup message
        try:
            now = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M")
            await self.client.send_message(
                CHANNEL_ID,
                f"🤖 WorldTimer started\n📅 {now}"
            )
        except Exception as e:
            print(f"⚠️ Could not send startup message: {e}")
        
        # Main loop
        try:
            while True:
                now = datetime.now(ZoneInfo(TIMEZONE))
                
                # 1. Check HOLIDAYS first (they take precedence)
                holiday_event = self.get_holiday_event(now)
                if holiday_event:
                    if self.should_send_special(holiday_event, now):
                        await self.send_event(holiday_event)
                    
                    # On holidays, only send holiday and special events
                    for special in self.get_special_events(now):
                        if self.should_send_special(special, now):
                            await self.send_event(special)
                    
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue
                
                # 2. Check WEEKEND events
                weekend_sent = False
                for event in self.events:
                    if event.get("condition") == "weekend":
                        if self.should_send_weekend_event(event, now):
                            await self.send_event(event)
                            weekend_sent = True
                
                # If weekend and not a weekend event, skip normal events
                if self.is_weekend_closed(now) and not weekend_sent:
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue
                
                # 3. Check SPECIAL DAYS (always send)
                for special in self.get_special_events(now):
                    if self.should_send_special(special, now):
                        await self.send_event(special)
                
                # 4. Check NORMAL DAY events
                for event in self.events:
                    if event.get("type") == "normal":
                        if self.should_send_normal(event, now):
                            await self.send_event(event)
                
                await asyncio.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
        finally:
            await self.client.disconnect()
            print("👋 Goodbye")

async def main():
    timer = WorldTimer()
    
    if not timer.load_events():
        return
    
    await timer.run()

if __name__ == "__main__":
    asyncio.run(main())