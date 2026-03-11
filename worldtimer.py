#!/usr/bin/env python3
"""
WorldTimer - Telegram bot that posts scheduled reminders to a channel
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
        self.holidays = []
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
        self.holidays = data.get("holidays", [])
        print(f"✅ Loaded {len(self.events)} events")
        return True
    
    def is_holiday(self, dt: datetime) -> bool:
        """Check if today is a holiday"""
        return dt.strftime("%Y-%m-%d") in self.holidays
    
    def should_send(self, event: dict, now: datetime) -> bool:
        """Check if event or its advance reminder should be sent now"""
        # Anti-spam: don't send same event twice in 5 minutes
        last = self.last_sent.get(event["id"])
        if last and (now - last).total_seconds() < 300:
            return False
        
        # Parse event time
        event_time = datetime.strptime(event["time"], "%H:%M").time()
        event_dt = datetime.combine(now.date(), event_time)
        event_dt = event_dt.replace(tzinfo=now.tzinfo)
        
        # Check if it's time for the main event
        if now.hour == event_time.hour and now.minute == event_time.minute:
            return True
        
        # Check advance reminder (if specified)
        if "advance" in event:
            advance_minutes = event["advance"]
            advance_dt = event_dt - timedelta(minutes=advance_minutes)
            
            # Only send advance if it's for today (not yesterday)
            if advance_dt.date() == now.date():
                if (now.hour == advance_dt.hour and 
                    now.minute == advance_dt.minute):
                    return True
        
        return False
    
    async def send_event(self, event: dict):
        """Send event message to channel"""
        try:
            now = datetime.now(ZoneInfo(TIMEZONE))
            event_time = datetime.strptime(event["time"], "%H:%M").time()
            event_dt = datetime.combine(now.date(), event_time)
            event_dt = event_dt.replace(tzinfo=now.tzinfo)
            
            # Check if this is an advance reminder
            is_advance = False
            advance_minutes = 0
            
            if "advance" in event:
                advance_minutes = event["advance"]
                advance_dt = event_dt - timedelta(minutes=advance_minutes)
                
                if (now.hour == advance_dt.hour and 
                    now.minute == advance_dt.minute):
                    is_advance = True
            
            # Build message
            if is_advance:
                if advance_minutes >= 60:
                    hours = advance_minutes // 60
                    time_text = f"{hours} hour{'s' if hours > 1 else ''}"
                else:
                    time_text = f"{advance_minutes} minutes"
                    
                msg = f"⏰ {time_text} until {event['name']}\n\n{event['message']}\n\n🕒 Happens at {event['time']}"
            else:
                msg = f"{event['message']}\n\n⏰ {event['time']}"
            
            # Send
            await self.client.send_message(CHANNEL_ID, msg)
            print(f"📤 {event['name']} sent {'(advance)' if is_advance else ''}")
            
            # Update last sent time
            self.last_sent[event["id"]] = datetime.now(ZoneInfo("UTC"))
            
        except Exception as e:
            print(f"❌ Failed to send {event['id']}: {e}")
    
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
        except:
            pass
        
        # Main loop
        try:
            while True:
                now = datetime.now(ZoneInfo(TIMEZONE))
                
                # Skip holidays if you want (remove this if you don't)
                if not self.is_holiday(now):
                    for event in self.events:
                        if self.should_send(event, now):
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