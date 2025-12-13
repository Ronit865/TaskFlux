"""
Test Notifications for TaskFlux Bot
====================================
This test file allows you to test individual notification types
to ensure they are displayed correctly in your ntfy client.

Run this to verify:
- Notification formatting
- Priority levels
- Emoji display
- Message content
"""

import requests
import time
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pytz

# Load environment variables
load_dotenv()


class NotificationTester:
    def __init__(self):
        self.ntfy_url = os.getenv("NTFY_URL")
        if not self.ntfy_url:
            raise ValueError("❌ NTFY_URL not found in .env file!")
        
        print(f"✅ NTFY URL loaded: {self.ntfy_url}")
    
    def send_notification(self, title, message, priority="default", tags=None):
        """Send notification via ntfy"""
        try:
            # Clean title for HTTP header compatibility
            clean_title = title.encode('latin-1', errors='ignore').decode('latin-1').strip()
            if not clean_title:
                clean_title = "TaskFlux Test"
            
            headers = {
                "Priority": priority,
                "Title": clean_title,
                "Content-Type": "text/plain; charset=utf-8"
            }
            if tags:
                headers["Tags"] = tags
            
            # Full message with emojis
            full_message = f"{title}\n\n{message}" if title != clean_title else message
            
            response = requests.post(
                self.ntfy_url,
                data=full_message.encode('utf-8'),
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Sent: {clean_title}")
                return True
            else:
                print(f"❌ Failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def test_all_notifications(self):
        """Test all notification types used in TaskFlux bot"""
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        future_time = current_time + timedelta(hours=6)
        cooldown_time = current_time + timedelta(hours=24)
        
        print("\n" + "="*70)
        print("🧪 TESTING ALL TASKFLUX NOTIFICATIONS")
        print("="*70)
        print("\nThis will send all notification types to test formatting.")
        print("Check your ntfy client after each notification.\n")
        
        tests = [
            # === LOGIN & STARTUP ===
            {
                "name": "1. Bot Started",
                "title": "Bot Started",
                "message": f"🧑‍💻 {os.getenv('EMAIL', 'test@example.com')}",
                "priority": "default",
                "tags": "robot"
            },
            {
                "name": "2. Login Failed (HTTP Error)",
                "title": "Login Failed",
                "message": f"❌ HTTP 401\n🔄 All 3 attempts failed",
                "priority": "urgent",
                "tags": "x"
            },
            {
                "name": "3. Login Timeout",
                "title": "Login Timeout",
                "message": f"❌ Server not responding\n🔄 All 3 attempts failed",
                "priority": "urgent",
                "tags": "x"
            },
            {
                "name": "4. Login Error",
                "title": "Login Error",
                "message": f"❌ Connection failed\n🔄 All 3 attempts failed",
                "priority": "urgent",
                "tags": "x"
            },
            {
                "name": "5. Bot Ready",
                "title": "Bot Ready",
                "message": f"🟢 Searching\n🕐 {current_time.strftime('%I:%M %p IST')}",
                "priority": "high",
                "tags": "green_circle"
            },
            
            # === TASK CLAIMING ===
            {
                "name": "6. Task Assigned",
                "title": "Task Assigned",
                "message": f"🎯 REDDITCOMMENTTASK\n💵 $2.00\n⏰ {future_time.strftime('%I:%M %p IST')}\n⏳ Time Left: 6.0h",
                "priority": "urgent",
                "tags": "dart"
            },
            {
                "name": "7. Assigned Task Found",
                "title": "Assigned Task Found",
                "message": f"📋 RedditCommentTask\n💵 $2.00\n🕐 {future_time.strftime('%I:%M %p IST')}\n⏳ 5.2h left",
                "priority": "urgent",
                "tags": "pushpin"
            },
            {
                "name": "8. Task Check Summary",
                "title": "Task Check Summary",
                "message": f"📊 Task Check Summary\n\n🔍 Total Found: 5\n✅ Claimable: 3\n🚫 Rejected: 2\n🎯 Claimed: 1\n\nTask details sent separately!",
                "priority": "default",
                "tags": "clipboard"
            },
            {
                "name": "9. No Claimable Tasks",
                "title": "No Claimable Tasks",
                "message": f"🔍 3 found\n🚫 All rejected\n\n• Wrong task type: 2\n• Unsafe content: 1\n\n⏱️ Retry in 3s",
                "priority": "low",
                "tags": "mag"
            },
            
            # === TASK DEADLINE WARNINGS ===
            {
                "name": "10. 2 Hours Left",
                "title": "2 Hours Left",
                "message": f"⚠️ 2.0h\n🕐 {future_time.strftime('%I:%M %p IST')}",
                "priority": "high",
                "tags": "warning"
            },
            {
                "name": "11. 30 Minutes Left",
                "title": "30 Minutes Left",
                "message": f"🚨 30min\n🕐 {future_time.strftime('%I:%M %p IST')}",
                "priority": "urgent",
                "tags": "fire"
            },
            {
                "name": "12. Deadline Exceeded",
                "title": "Deadline Exceeded",
                "message": f"⛔ {future_time.strftime('%I:%M %p IST')}",
                "priority": "urgent",
                "tags": "no_entry"
            },
            {
                "name": "13. Task Deadline Passed",
                "title": "Task Deadline Passed",
                "message": f"⛔ RedditCommentTask\n💵 $2.00\n🕐 {future_time.strftime('%I:%M %p IST')}",
                "priority": "urgent",
                "tags": "no_entry"
            },
            
            # === TASK COMPLETION ===
            {
                "name": "14. Task Submitted",
                "title": "Task Submitted",
                "message": f"🎯 $2.00",
                "priority": "high",
                "tags": "dart"
            },
            
            # === COOLDOWN MONITORING ===
            {
                "name": "15. Cooldown Started",
                "title": "Cooldown Started",
                "message": f"⌛ 24h\n🕐 {cooldown_time.strftime('%I:%M %p IST')}",
                "priority": "default",
                "tags": "hourglass"
            },
            {
                "name": "16. Cooldown Active",
                "title": "Cooldown Active",
                "message": f"⌛ 23.5h\n🕐 {cooldown_time.strftime('%I:%M %p IST')}",
                "priority": "default",
                "tags": "hourglass"
            },
            {
                "name": "17. 1 Hour Left",
                "title": "1 Hour Left",
                "message": f"⏰ 60min\n🕐 {cooldown_time.strftime('%I:%M %p IST')}",
                "priority": "high",
                "tags": "alarm_clock"
            },
            {
                "name": "18. 10 Minutes Left",
                "title": "10 Minutes Left",
                "message": f"⏰ 10min\n🕐 {cooldown_time.strftime('%I:%M %p IST')}",
                "priority": "high",
                "tags": "alarm_clock"
            },
            {
                "name": "19. 5 Minutes Left",
                "title": "5 Minutes Left",
                "message": f"⏰ 5min\n🕐 {cooldown_time.strftime('%I:%M %p IST')}",
                "priority": "high",
                "tags": "bell"
            },
            {
                "name": "20. Cooldown Ending",
                "title": "Cooldown Ending",
                "message": f"🔥 2min\n🕐 {cooldown_time.strftime('%I:%M %p IST')}",
                "priority": "urgent",
                "tags": "fire"
            },
            
            # === TIME-BASED OPERATIONS ===
            {
                "name": "21. Off-Hours Sleep",
                "title": "Off-Hours Sleep",
                "message": f"😴 8.5h\n⏰ 08:00 AM IST\n🕐 Claiming: 8 AM - 11 PM",
                "priority": "default",
                "tags": "zzz"
            },
            {
                "name": "22. Bot Awake",
                "title": "Bot Awake",
                "message": f"☀️ Ready!\n🕐 08:00 AM IST",
                "priority": "high",
                "tags": "sunny"
            },
            
            # === ERROR & SYSTEM ===
            {
                "name": "23. Bot Stopped",
                "title": "Bot Stopped",
                "message": f"💀 Stopped\n🕐 {current_time.strftime('%I:%M %p IST')}",
                "priority": "default",
                "tags": "robot"
            },
            {
                "name": "24. Bot Crashed",
                "title": "Bot Crashed",
                "message": f"💥 Critical Error\n⚠️ Connection timeout\n🕐 {current_time.strftime('%I:%M %p IST')}",
                "priority": "urgent",
                "tags": "x"
            }
        ]
        
        print(f"📤 Sending {len(tests)} test notifications...\n")
        print("⏳ This will take ~50 seconds (2 seconds between each notification)\n")
        
        success_count = 0
        for i, test in enumerate(tests, 1):
            print(f"\n{'─'*70}")
            print(f"Test {i}/{len(tests)}: {test['name']}")
            print(f"Priority: {test['priority'].upper()}")
            print(f"{'─'*70}")
            
            success = self.send_notification(
                test['title'],
                test['message'],
                test['priority'],
                test['tags']
            )
            
            if success:
                success_count += 1
            
            # Wait 2 seconds between notifications
            if i < len(tests):
                print("⏳ Waiting 2 seconds...")
                time.sleep(2)
        
        print(f"\n{'='*70}")
        print(f"✅ TEST COMPLETED: {success_count}/{len(tests)} notifications sent")
        print("="*70)
        print("\n📱 Check your ntfy client to verify all notifications!")
        print("\n")
    
    def test_single_notification(self):
        """Test a single notification"""
        print("\n" + "="*70)
        print("🧪 SINGLE NOTIFICATION TEST")
        print("="*70)
        print("\nThis will send a simple test notification.\n")
        
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        
        success = self.send_notification(
            "Test Notification",
            f"🧪 This is a test\n🕐 {current_time.strftime('%I:%M:%S %p IST')}",
            "default",
            "white_check_mark"
        )
        
        if success:
            print("\n✅ Test notification sent successfully!")
            print("📱 Check your ntfy client!\n")
        else:
            print("\n❌ Failed to send test notification.\n")
    
    def test_priority_levels(self):
        """Test different priority levels"""
        print("\n" + "="*70)
        print("🧪 TESTING PRIORITY LEVELS")
        print("="*70)
        print("\nThis will send 5 notifications with different priorities.\n")
        
        priorities = [
            ("min", "Minimum Priority", "🔇"),
            ("low", "Low Priority", "🔉"),
            ("default", "Default Priority", "🔔"),
            ("high", "High Priority", "📢"),
            ("urgent", "Urgent Priority", "🚨")
        ]
        
        for priority, title, emoji in priorities:
            print(f"Sending {priority.upper()} priority...")
            self.send_notification(
                title,
                f"{emoji} This is a {priority} priority notification",
                priority,
                "bell"
            )
            time.sleep(2)
        
        print("\n✅ All priority levels sent!")
        print("📱 Check your ntfy client to see the differences!\n")
    
    def test_cooldown_alerts(self):
        """Test cooldown alert notifications"""
        print("\n" + "="*70)
        print("🧪 TESTING COOLDOWN ALERTS")
        print("="*70)
        print("\nThis will send all 5 cooldown-related notifications.\n")
        
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        cooldown_end = current_time + timedelta(hours=1)
        
        alerts = [
            {
                "title": "Cooldown Started",
                "message": f"⌛ 24h\n🕐 {cooldown_end.strftime('%I:%M %p IST')}",
                "priority": "default"
            },
            {
                "title": "1 Hour Left",
                "message": f"⏰ 60min\n🕐 {cooldown_end.strftime('%I:%M %p IST')}",
                "priority": "high"
            },
            {
                "title": "10 Minutes Left",
                "message": f"⏰ 10min\n🕐 {cooldown_end.strftime('%I:%M %p IST')}",
                "priority": "high"
            },
            {
                "title": "5 Minutes Left",
                "message": f"⏰ 5min\n🕐 {cooldown_end.strftime('%I:%M %p IST')}",
                "priority": "high"
            },
            {
                "title": "Cooldown Ending",
                "message": f"🔥 2min\n🕐 {cooldown_end.strftime('%I:%M %p IST')}",
                "priority": "urgent"
            }
        ]
        
        for i, alert in enumerate(alerts, 1):
            print(f"\n{i}/5: Sending {alert['title']} ({alert['priority'].upper()})...")
            self.send_notification(
                alert['title'],
                alert['message'],
                alert['priority'],
                "alarm_clock"
            )
            if i < len(alerts):
                time.sleep(2)
        
        print("\n✅ All cooldown alerts sent!")
        print("📱 Check your ntfy client!\n")


def main():
    """Main test menu"""
    print("\n" + "="*70)
    print("🧪 TASKFLUX NOTIFICATION TESTER")
    print("="*70)
    
    try:
        tester = NotificationTester()
    except ValueError as e:
        print(f"\n{e}")
        print("\nPlease add NTFY_URL to your .env file.")
        print("Example: NTFY_URL=https://ntfy.sh/your-topic\n")
        return
    
    while True:
        print("\n" + "="*70)
        print("📋 TEST MENU")
        print("="*70)
        print("\n1. Test Single Notification")
        print("2. Test All Notification Types (24 notifications)")
        print("3. Test Priority Levels (5 notifications)")
        print("4. Test Cooldown Alerts Only (5 notifications)")
        print("5. Exit")
        print("\n" + "="*70)
        
        choice = input("\n👉 Enter your choice (1-5): ").strip()
        
        if choice == "1":
            tester.test_single_notification()
        elif choice == "2":
            print("\n⚠️ This will send 24 notifications over ~50 seconds.")
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                tester.test_all_notifications()
        elif choice == "3":
            tester.test_priority_levels()
        elif choice == "4":
            tester.test_cooldown_alerts()
        elif choice == "5":
            print("\n👋 Goodbye!\n")
            break
        else:
            print("\n❌ Invalid choice. Please enter 1-5.")


if __name__ == "__main__":
    main()
