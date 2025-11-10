import requests
import time
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import pytz
from task_claimer import TaskClaimer

# Load environment variables
load_dotenv()

class ContinuousTaskChecker:
    def __init__(self):
        self.base_url = "https://taskflux.net"
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")
        self.ntfy_url = os.getenv("NTFY_URL")
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        
        # Initialize task claimer (will be set after login)
        self.task_claimer = None
        
        # Rapid checking intervals for continuous mode (in seconds)
        self.min_check_interval = 3    # 3 seconds minimum
        self.max_check_interval = 30   # 30 seconds maximum
        self.current_check_interval = 3  # Start with 3 seconds
        
        # Task availability tracking
        self.consecutive_empty_checks = 0
        self.last_task_seen = None
        self.tasks_seen_today = 0
        
        # Suspicious words/patterns that might trigger AutoMod or get removed
        self.suspicious_patterns = [
            # Spam-like patterns
            'click here', 'free money', 'make money fast', 'get rich', 'earn money',
            'work from home', 'passive income', 'easy money', 'quick cash',
            
            # Promotional/commercial
            'buy now', 'limited time', 'act now', 'don\'t miss', 'special offer',
            'discount code', 'promo code', 'affiliate', 'referral link',
            
            # Suspicious links
            'bit.ly', 'tinyurl', 'shortened link', 'goo.gl',
            
            # Common spam triggers
            'dm me', 'pm me for', 'message me', 'whatsapp', 'telegram',
            'crypto', 'bitcoin', 'forex', 'trading signals', 'investment opportunity',
            
            # Self-promotion flags
            'check out my', 'subscribe to my', 'follow me', 'my channel',
            'my youtube', 'my instagram', 'my tiktok', 'my website',
            
            # Low-effort content
            'upvote if', 'upvote this', 'give me karma', 'need karma',
            
            # Potentially offensive/controversial
            'retard', 'stupid ass', 'dumb fuck', 'kill yourself',
            
            # Rule-breaking patterns
            'vote manipulation', 'brigade', 'spam', 'bot account'
        ]
    
    def send_notification(self, title, message, priority="default", tags=None):
        """Send notification via ntfy with retry logic"""
        if not self.ntfy_url:
            print(f"⚠️ No ntfy URL configured, skipping notification")
            return
            
        try:
            # Remove emojis and non-Latin-1 characters from title for HTTP header compatibility
            # HTTP headers must be Latin-1 compatible and cannot have leading/trailing whitespace
            clean_title = title.encode('latin-1', errors='ignore').decode('latin-1').strip()
            if not clean_title:
                clean_title = "TaskFlux Notification"
            
            headers = {
                "Priority": priority,
                "Title": clean_title,
                "Content-Type": "text/plain; charset=utf-8"
            }
            if tags:
                headers["Tags"] = tags
            
            # Send full message (including emojis) as UTF-8 encoded bytes
            # Include original title with emojis in the message body
            full_message = f"{title}\n\n{message}" if title != clean_title else message
            
            # Retry logic with timeout
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        self.ntfy_url,
                        data=full_message.encode('utf-8'),
                        headers=headers,
                        timeout=10  # 10 second timeout
                    )
                    
                    if response.status_code == 200:
                        return  # Success
                    else:
                        print(f"⚠️ Failed to send notification: {response.status_code}")
                        if attempt < max_retries - 1:
                            time.sleep(2)  # Wait before retry
                except requests.exceptions.RequestException as req_err:
                    if attempt < max_retries - 1:
                        print(f"⚠️ Network error (attempt {attempt + 1}/{max_retries}), retrying...")
                        time.sleep(2)
                    else:
                        print(f"⚠️ Failed to send notification after {max_retries} attempts: {req_err}")
                        
        except Exception as e:
            print(f"⚠️ Error sending notification: {e}")
    
    def login(self):
        """Login to TaskFlux"""
        try:
            print("\n" + "="*60)
            print(f"🔐 Logging in as {self.email}...")
            print("="*60)
            
            login_url = f"{self.base_url}/api/users/login"
            
            credentials = {
                "email": self.email,
                "password": self.password
            }
            
            response = self.session.post(login_url, json=credentials)
            
            if response.status_code == 200:
                data = response.json()
                self.user_id = data.get('user', {}).get('_id')
                print(f"✅ Login successful!")
                print(f"👤 User ID: {self.user_id}")
                
                # Initialize task claimer after successful login
                self.task_claimer = TaskClaimer(
                    self.base_url,
                    self.session,
                    self.user_id
                )
                
                # Send login notification
                ist = pytz.timezone('Asia/Kolkata')
                current_ist = datetime.now(ist)
                self.send_notification(
                    "Bot Started",
                    f"✅ {self.email} online!\nTime: {current_ist.strftime('%I:%M %p IST')}\n\n🔄 Continuous Task Checker active",
                    priority="default",
                    tags="white_check_mark"
                )
                
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def get_available_tasks(self):
        """Fetch available tasks from task-pool"""
        try:
            tasks_url = f"{self.base_url}/api/tasks/task-pool"
            response = self.session.get(tasks_url)
            
            if response.status_code == 200:
                data = response.json()
                all_tasks = data if isinstance(data, list) else data.get('tasks', [])
                
                # Filter out already assigned tasks
                available_tasks = []
                for task in all_tasks:
                    status = task.get('status', '').lower()
                    if status != 'assigned':
                        available_tasks.append(task)
                
                return available_tasks
            else:
                return []
                
        except Exception as e:
            print(f"⚠️ Error fetching tasks: {e}")
            return []
    
    def is_content_safe(self, content):
        """Check if task content is safe"""
        if not content:
            return True, "No content to check"
        
        content_lower = content.lower()
        
        for pattern in self.suspicious_patterns:
            if pattern.lower() in content_lower:
                return False, f"Contains suspicious pattern: '{pattern}'"
        
        letters = [c for c in content if c.isalpha()]
        if letters:
            caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if caps_ratio > 0.5 and len(letters) > 10:
                return False, "Excessive uppercase"
        
        special_chars = sum(1 for c in content if c in '!?$#@*')
        if len(content) > 0:
            special_ratio = special_chars / len(content)
            if special_ratio > 0.2:
                return False, "Excessive special characters"
        
        if len(content.strip()) < 10:
            return False, "Comment too short"
        
        for char in set(content):
            if content.count(char * 5) > 0:
                return False, f"Repetitive characters"
        
        return True, "Content appears safe"
    
    def check_and_notify_tasks(self):
        """Check for available tasks and send notification (no claiming)"""
        print(f"🔍 Checking for available tasks...")
        tasks = self.get_available_tasks()
        
        if not tasks:
            self.consecutive_empty_checks += 1
            print(f"📭 No tasks available (empty check #{self.consecutive_empty_checks})")
            return False
        
        if self.consecutive_empty_checks > 0:
            print(f"✨ Tasks appeared after {self.consecutive_empty_checks} empty checks!")
        
        self.consecutive_empty_checks = 0
        self.last_task_seen = datetime.now()
        self.tasks_seen_today += len(tasks)
        
        total_available = len(tasks)
        print(f"📋 Found {total_available} task(s) available")
        
        # Filter for allowed task types
        allowed_task_types = ['redditcommenttask', 'redditreplytask']
        claimable_tasks = []
        
        for task in tasks:
            task_type = task.get('type', '').lower()
            task_name = task.get('name', '').lower()
            
            type_matches = any(allowed_type in task_type or allowed_type in task_name 
                              for allowed_type in allowed_task_types)
            
            if type_matches:
                content = task.get('content', '') or task.get('comment', '')
                is_safe, reason = self.is_content_safe(content)
                
                if is_safe:
                    claimable_tasks.append(task)
        
        total_claimable = len(claimable_tasks)
        
        print(f"✅ Total Available: {total_available} | Total Claimable: {total_claimable}")
        
        # Send notification with task counts
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        
        notification_msg = f"📊 Task Status\n\n"
        notification_msg += f"📋 Total Available: {total_available}\n"
        notification_msg += f"✅ Total Claimable: {total_claimable}\n"
        notification_msg += f"⏰ Time: {current_time.strftime('%I:%M %p IST')}\n"
        
        if total_claimable > 0:
            notification_msg += f"\n🎯 {total_claimable} safe task{'s' if total_claimable != 1 else ''} ready to claim!"
            priority = "high"
            tags = "white_check_mark,bell"
        else:
            notification_msg += f"\n⚠️ No safe claimable tasks found"
            priority = "default"
            tags = "inbox_tray"
        
        self.send_notification(
            "📋 Tasks Found",
            notification_msg,
            priority=priority,
            tags=tags
        )
        
        return total_claimable > 0
    
    def check_and_claim_task(self):
        """Check for available tasks and claim the first safe one"""
        print(f"🔍 Checking for available tasks to claim...")
        tasks = self.get_available_tasks()
        
        if not tasks:
            self.consecutive_empty_checks += 1
            print(f"📭 No tasks available (empty check #{self.consecutive_empty_checks})")
            return False
        
        if self.consecutive_empty_checks > 0:
            print(f"✨ Tasks appeared after {self.consecutive_empty_checks} empty checks!")
        
        self.consecutive_empty_checks = 0
        self.last_task_seen = datetime.now()
        self.tasks_seen_today += len(tasks)
        
        total_available = len(tasks)
        print(f"📋 Found {total_available} task(s) available")
        
        # Filter for allowed task types
        allowed_task_types = ['redditcommenttask', 'redditreplytask']
        claimable_tasks = []
        
        for task in tasks:
            task_type = task.get('type', '').lower()
            task_name = task.get('name', '').lower()
            
            type_matches = any(allowed_type in task_type or allowed_type in task_name 
                              for allowed_type in allowed_task_types)
            
            if type_matches:
                content = task.get('content', '') or task.get('comment', '')
                is_safe, reason = self.is_content_safe(content)
                
                if is_safe:
                    claimable_tasks.append(task)
        
        total_claimable = len(claimable_tasks)
        
        print(f"✅ Total Available: {total_available} | Total Claimable: {total_claimable}")
        
        if not claimable_tasks:
            print(f"⚠️ No safe claimable tasks found!")
            return False
        
        # Claim the first safe task
        task = claimable_tasks[0]
        task_id = task.get('_id') or task.get('id') or task.get('taskId')
        
        if not task_id:
            print(f"❌ No task ID found!")
            return False
        
        print(f"🎯 CLAIMING FIRST SAFE TASK IMMEDIATELY...")
        
        # Use task claimer to claim the task
        if self.task_claimer:
            claimed = self.task_claimer.claim_task(
                task_id,
                task_details=task,
                notification_callback=self.send_notification
            )
            
            if claimed:
                print(f"✅ Task claimed successfully!")
                
                # Send summary notification
                summary_msg = f"📊 Task Claim Summary\n\n"
                summary_msg += f"📋 Total Found: {total_available}\n"
                summary_msg += f"✅ Claimable: {total_claimable}\n"
                summary_msg += f"🎯 Claimed: YES"
                
                self.send_notification(
                    "Task Claimed",
                    summary_msg,
                    priority="high",
                    tags="dart"
                )
                
                return True
            else:
                print(f"❌ Failed to claim task")
                return False
        else:
            print(f"❌ Task claimer not initialized!")
            return False
    
    def run(self):
        """Main continuous checking loop"""
        if not self.login():
            print("❌ Failed to login. Exiting...")
            return
        
        loop_count = 0
        
        print(f"\n{'='*60}")
        print(f"🚀 CONTINUOUS TASK CHECKER STARTED")
        print(f"{'='*60}")
        print(f"⚡ Mode: ULTRA RAPID (3 second checks)")
        print(f"🎯 Focus: Monitoring tasks and sending notifications")
        print(f"{'='*60}\n")
        
        try:
            while True:
                try:
                    loop_count += 1
                    current_time = datetime.now().strftime('%I:%M:%S %p')
                    
                    print(f"\n{'='*60}")
                    print(f"🔄 CHECK #{loop_count} - {current_time}")
                    print(f"{'='*60}")
                    
                    # Check tasks and send notifications
                    found_claimable = self.check_and_notify_tasks()
                    
                    # Always use 3 second interval
                    sleep_time = 3
                    
                    if found_claimable:
                        print(f"✅ Claimable tasks found! Checking again in {sleep_time}s")
                    else:
                        print(f"💤 Sleeping for {sleep_time}s...")
                    
                    next_check = datetime.now() + timedelta(seconds=sleep_time)
                    print(f"⏰ Next check: #{loop_count + 1} at {next_check.strftime('%I:%M:%S %p')}")
                    
                    time.sleep(sleep_time)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"⚠️ Error in main loop: {e}")
                    print(f"🔄 Retrying in 60 seconds...")
                    time.sleep(60)
                    
        except KeyboardInterrupt:
            print(f"\n🛑 Bot stopped by user")
            print(f"📊 Total checks performed: {loop_count}")
            
            self.send_notification(
                "Bot Stopped",
                f"❎ Continuous checker stopped\nTotal checks: {loop_count}",
                priority="default",
                tags="stop_sign"
            )

if __name__ == "__main__":
    bot = ContinuousTaskChecker()
    bot.run()
