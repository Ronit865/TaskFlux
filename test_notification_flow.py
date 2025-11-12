"""
Test Notification Flow
======================
This test file simulates a complete task flow to test all notifications:

TIMELINE:
---------
0:00 - Start with 2 min left in cooldown
2:00 - Cooldown completes → "Ready" notification
3:00 - 3 tasks found (2 safe, 1 unsafe) → "Task Check Summary" + "Task Assigned" notification
7:00 - Task submitted → "Task Submitted" + "Cooldown Started" notification

This simulates real bot behavior to test the notification system.
"""

import requests
import time
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import pytz

# Load environment variables
load_dotenv()


class NotificationTestBot:
    def __init__(self):
        self.base_url = "https://taskflux.net"
        self.ntfy_url = os.getenv("NTFY_URL")
        self.cooldown_file = "cooldown.json"
        self.cooldown_end = None
        
    def send_notification(self, title, message, priority="default", tags=None):
        """Send notification via ntfy"""
        if not self.ntfy_url:
            print(f"⚠️ No ntfy URL configured, skipping notification")
            return
            
        try:
            clean_title = title.encode('latin-1', errors='ignore').decode('latin-1').strip()
            if not clean_title:
                clean_title = "TaskFlux Test Notification"
            
            headers = {
                "Priority": priority,
                "Title": clean_title,
                "Content-Type": "text/plain; charset=utf-8"
            }
            if tags:
                headers["Tags"] = tags
            
            full_message = f"{title}\n\n{message}" if title != clean_title else message
            
            response = requests.post(
                self.ntfy_url,
                data=full_message.encode('utf-8'),
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Notification sent: {clean_title}")
            else:
                print(f"⚠️ Failed to send notification: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Error sending notification: {e}")
    
    def save_cooldown(self, cooldown_end):
        """Save cooldown to file"""
        try:
            self.cooldown_end = cooldown_end
            with open(self.cooldown_file, 'w') as f:
                if cooldown_end is None:
                    json.dump({}, f)
                else:
                    json.dump({'cooldown_end': cooldown_end.isoformat()}, f)
            print(f"💾 Cooldown saved: {cooldown_end.strftime('%I:%M:%S %p IST') if cooldown_end else 'None'}")
        except Exception as e:
            print(f"⚠️ Error saving cooldown: {e}")
    
    def run_test(self):
        """Run the complete notification test flow"""
        ist = pytz.timezone('Asia/Kolkata')
        
        print("\n" + "="*70)
        print("🧪 NOTIFICATION FLOW TEST STARTED")
        print("="*70)
        print("This test simulates a complete task flow with notifications:")
        print("  • T+0:00 - Start with 2 min left in cooldown")
        print("  • T+2:00 - Cooldown completes")
        print("  • T+3:00 - 3 tasks found (2 safe)")
        print("  • T+7:00 - Task submitted")
        print("="*70 + "\n")
        
        # ═══════════════════════════════════════════════════════════
        # PHASE 1: Initial State - 2 minutes left in cooldown
        # ═══════════════════════════════════════════════════════════
        print("\n" + "="*70)
        print("⏰ PHASE 1: COOLDOWN ACTIVE (2 minutes remaining)")
        print("="*70)
        
        # Set cooldown to end in 2 minutes
        cooldown_end = datetime.now() + timedelta(minutes=2)
        self.save_cooldown(cooldown_end)
        
        current_time = datetime.now(ist)
        print(f"🕐 Current Time: {current_time.strftime('%I:%M:%S %p IST')}")
        print(f"⏰ Cooldown End: {cooldown_end.strftime('%I:%M:%S %p IST')}")
        print(f"⏳ Time Remaining: 2.0 minutes")
        
        # Send cooldown active notification
        self.send_notification(
            "Cooldown Active",
            f"⌛ 2.0h left\n🕐 {cooldown_end.strftime('%I:%M %p IST')}",
            priority="default",
            tags="hourglass"
        )
        
        print(f"\n💤 Waiting 2 minutes for cooldown to complete...")
        print(f"{'─'*70}")
        
        # Show countdown
        for remaining in range(120, 0, -30):
            mins = remaining // 60
            secs = remaining % 60
            print(f"⏳ {mins}m {secs}s remaining...")
            time.sleep(30)
        
        print(f"{'─'*70}")
        
        # ═══════════════════════════════════════════════════════════
        # PHASE 2: Cooldown Complete
        # ═══════════════════════════════════════════════════════════
        print("\n" + "="*70)
        print("✅ PHASE 2: COOLDOWN COMPLETED")
        print("="*70)
        
        # Clear cooldown
        self.save_cooldown(None)
        
        current_time = datetime.now(ist)
        print(f"🕐 Current Time: {current_time.strftime('%I:%M:%S %p IST')}")
        print(f"✅ Cooldown completed!")
        
        # Send "Ready" notification
        self.send_notification(
            "Ready",
            f"🔥 Cooldown ended",
            priority="high",
            tags="robot"
        )
        
        print(f"\n💤 Waiting 1 minute before checking tasks...")
        print(f"{'─'*70}")
        time.sleep(60)
        print(f"{'─'*70}")
        
        # ═══════════════════════════════════════════════════════════
        # PHASE 3: Tasks Found (2 Safe, 1 Unsafe)
        # ═══════════════════════════════════════════════════════════
        print("\n" + "="*70)
        print("🔍 PHASE 3: TASKS FOUND (2 Safe, 1 Unsafe)")
        print("="*70)
        
        current_time = datetime.now(ist)
        print(f"🕐 Current Time: {current_time.strftime('%I:%M:%S %p IST')}")
        print(f"\n📋 Task Discovery:")
        print(f"   Total Found: 3")
        print(f"   Safe Tasks: 2")
        print(f"   Unsafe Tasks: 1 (rejected - suspicious content)")
        print(f"   Claimed: 1 (first safe task)")
        
        # Send task check summary notification
        summary_msg = "📊 Task Check Summary\n\n"
        summary_msg += "🔍 Total Found: 3\n"
        summary_msg += "✅ Claimable: 2\n"
        summary_msg += "🚫 Rejected: 1\n"
        summary_msg += "🎯 Claimed: 1"
        summary_msg += "\n\nTask details sent separately!"
        
        self.send_notification(
            "Task Check Summary",
            summary_msg,
            priority="default",
            tags="clipboard"
        )
        
        print(f"\n⏳ Waiting 2 seconds before task assignment notification...")
        time.sleep(2)
        
        # Calculate deadline (6 hours from now)
        claim_time = datetime.now(ist)
        deadline_time = claim_time + timedelta(hours=6)
        
        print(f"\n🎯 Task Claimed:")
        print(f"   Type: RedditCommentTask")
        print(f"   Price: $2.00")
        print(f"   Claimed: {claim_time.strftime('%I:%M:%S %p IST')}")
        print(f"   Deadline: {deadline_time.strftime('%I:%M %p IST')} (6 hours)")
        
        # Send task assigned notification
        task_info = "🎯 Type: REDDITCOMMENTTASK\n"
        task_info += "💵 Price: $2.00\n"
        task_info += f"⏰ Deadline: {deadline_time.strftime('%I:%M %p IST')}\n"
        task_info += "⏳ Time Left: 6.0h"
        
        self.send_notification(
            "Task Assigned",
            task_info,
            priority="urgent",
            tags="dart"
        )
        
        print(f"\n💤 Waiting 4 minutes before task submission...")
        print(f"{'─'*70}")
        
        # Show countdown (4 minutes = 240 seconds)
        for remaining in range(240, 0, -60):
            mins = remaining // 60
            print(f"⏳ {mins}m remaining...")
            time.sleep(60)
        
        print(f"{'─'*70}")
        
        # ═══════════════════════════════════════════════════════════
        # PHASE 4: Task Submitted
        # ═══════════════════════════════════════════════════════════
        print("\n" + "="*70)
        print("✅ PHASE 4: TASK SUBMITTED")
        print("="*70)
        
        current_time = datetime.now(ist)
        print(f"🕐 Current Time: {current_time.strftime('%I:%M:%S %p IST')}")
        print(f"✅ Task submitted successfully!")
        print(f"💰 Total Amount: $2.00")
        
        # Send task submitted notification
        self.send_notification(
            "Task Submitted",
            "🎯 $2.00",
            priority="high",
            tags="dart"
        )
        
        print(f"\n⏳ Waiting 30 seconds before cooldown notification...")
        time.sleep(30)
        
        # Start new 24-hour cooldown
        new_cooldown_end = datetime.now() + timedelta(hours=24)
        self.save_cooldown(new_cooldown_end)
        
        print(f"\n⏰ New Cooldown Started:")
        print(f"   Duration: 24 hours")
        print(f"   End Time: {new_cooldown_end.strftime('%I:%M %p IST on %B %d')}")
        
        # Send cooldown started notification
        self.send_notification(
            "Cooldown Started",
            f"⌛ 24h\n🕐 {new_cooldown_end.strftime('%I:%M %p IST')}",
            priority="default",
            tags="hourglass"
        )
        
        # ═══════════════════════════════════════════════════════════
        # TEST COMPLETE
        # ═══════════════════════════════════════════════════════════
        print("\n" + "="*70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*70)
        print("\n📊 NOTIFICATIONS SENT:")
        print("   1. ⏰ Cooldown Active (2 min remaining)")
        print("   2. ✅ Ready (Cooldown ended)")
        print("   3. 📋 Task Check Summary (3 found, 2 safe)")
        print("   4. 🎯 Task Assigned ($2.00, 6h deadline)")
        print("   5. ✅ Task Submitted ($2.00)")
        print("   6. ⏰ Cooldown Started (24h)")
        print(f"\n{'='*70}")
        print("🎉 All notifications sent! Check your ntfy client.")
        print("="*70 + "\n")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 TASKFLUX NOTIFICATION TEST")
    print("="*70)
    print("\nThis test will simulate a complete task flow to test notifications.")
    print("The test will take approximately 7 minutes to complete.")
    print("\nMake sure you have:")
    print("  ✓ NTFY_URL configured in .env file")
    print("  ✓ ntfy app/client ready to receive notifications")
    print("\n" + "="*70)
    
    input("\n⏎ Press ENTER to start the test...")
    
    bot = NotificationTestBot()
    bot.run_test()
