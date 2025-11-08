import requests
import time
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import pytz

# Load environment variables
load_dotenv()

class TaskFluxBot:
    def __init__(self):
        self.base_url = "https://taskflux.net"
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")
        self.ntfy_url = os.getenv("NTFY_URL")
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        self.cooldown_end = None
        self.cooldown_file = "cooldown.json"
        
        # Checking interval (in seconds)
        # IMPORTANT: Tasks are PUBLIC and disappear FAST (seconds/minutes)
        # Faster checking = better chance to claim before others
        self.min_check_interval = 3    # 3 seconds
        self.max_check_interval = 3    # 3 seconds (fixed interval)
        self.current_check_interval = 3  # Start with 3 seconds
        
        # Task availability tracking
        self.consecutive_empty_checks = 0
        self.last_task_seen = None
        self.tasks_seen_today = 0
        
        # Task deadline tracking (6-hour completion limit)
        self.task_claimed_at = None
        self.task_deadline = None
        self.deadline_warning_sent = False
        self.deadline_final_warning_sent = False
        self.current_task_id = None  # Track current assigned task ID
        self.current_task_type = None  # Track current task type (RedditCommentTask or RedditReplyTask)
        
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
            
            # Potentially offensive/controversial (add more as needed)
            'retard', 'stupid ass', 'dumb fuck', 'kill yourself',
            
            # Rule-breaking patterns
            'vote manipulation', 'brigade', 'spam', 'bot account'
        ]
        
        # Load saved cooldown info
        self.load_cooldown()
    
    def load_cooldown(self):
        """Load cooldown information from file"""
        try:
            if os.path.exists(self.cooldown_file):
                with open(self.cooldown_file, 'r') as f:
                    content = f.read().strip()
                    if content:  # Only parse if file is not empty
                        data = json.loads(content)
                        cooldown_str = data.get('cooldown_end')
                        if cooldown_str:
                            self.cooldown_end = datetime.fromisoformat(cooldown_str)
        except json.JSONDecodeError:
            # File is empty or corrupted, ignore and continue
            pass
        except Exception as e:
            print(f"⚠️ Error loading cooldown: {e}")
    
    def save_cooldown(self, cooldown_end):
        """Save cooldown information to file"""
        try:
            self.cooldown_end = cooldown_end
            with open(self.cooldown_file, 'w') as f:
                if cooldown_end is None:
                    json.dump({}, f)  # Write empty object instead of null
                else:
                    json.dump({'cooldown_end': cooldown_end.isoformat()}, f)
        except Exception as e:
            print(f"⚠️ Error saving cooldown: {e}")
    
    def is_in_cooldown(self):
        """Check if currently in cooldown period"""
        if self.cooldown_end is None:
            return False
        return datetime.now() < self.cooldown_end
    
    def get_cooldown_remaining(self):
        """Get remaining cooldown time"""
        if self.cooldown_end is None:
            return None
        remaining = self.cooldown_end - datetime.now()
        if remaining.total_seconds() <= 0:
            return None
        return remaining
    
    def send_notification(self, title, message, priority="default", tags=None):
        """Send notification via ntfy"""
        try:
            # Remove emojis and non-Latin-1 characters from title for HTTP header compatibility
            # HTTP headers must be Latin-1 compatible and cannot have leading/trailing whitespace
            clean_title = title.encode('latin-1', errors='ignore').decode('latin-1').strip()
            if not clean_title:
                # If title becomes empty after removing emojis, use a default
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
            
            response = requests.post(
                self.ntfy_url,
                data=full_message.encode('utf-8'),
                headers=headers
            )
            
            if response.status_code != 200:
                print(f"⚠️ Failed to send notification: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Error sending notification: {e}")
    
    def login(self):
        """Login to TaskFlux"""
        try:
            print("\n" + "="*60)
            print(f"🔐 Logging in as {self.email}...")
            print("="*60)
            
            # Actual TaskFlux login endpoint
            login_url = f"{self.base_url}/api/users/login"
            
            payload = {
                "email": self.email,
                "password": self.password
            }
            
            response = self.session.post(login_url, json=payload)
            
            if response.status_code == 200:
                # TaskFlux uses cookie-based authentication (accessToken cookie)
                # The session automatically handles cookies, no need to manually set headers
                
                # Try to get user data from response
                user_data = None
                has_assigned_task = False
                try:
                    data = response.json()
                    if 'user' in data:
                        user_data = data['user']
                        self.user_id = user_data.get('_id') or user_data.get('id')
                        
                        # Check if user has assigned task in login response
                        assigned_task = user_data.get('assignedTask') or user_data.get('currentTask')
                        if assigned_task:
                            has_assigned_task = True
                            
                            # Try to extract task details
                            task_id = assigned_task.get('id') or assigned_task.get('_id', 'unknown')
                            task_type = assigned_task.get('type', 'N/A')
                            created_at = assigned_task.get('createdAt') or assigned_task.get('claimedAt')
                            
                            # Set up deadline tracking if we have creation time
                            if created_at:
                                try:
                                    ist = pytz.timezone('Asia/Kolkata')
                                    claimed_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                    
                                    if claimed_time.tzinfo:
                                        claimed_time_ist = claimed_time.astimezone(ist)
                                        claimed_time = claimed_time_ist.replace(tzinfo=None)
                                    else:
                                        utc = pytz.UTC
                                        claimed_time = utc.localize(claimed_time).astimezone(ist).replace(tzinfo=None)
                                    
                                    deadline_time = claimed_time + timedelta(hours=6)
                                    
                                    self.task_claimed_at = claimed_time
                                    self.task_deadline = deadline_time
                                except Exception as e:
                                    pass
                    elif '_id' in data:
                        self.user_id = data.get('_id')
                        user_data = data
                except:
                    # Response might be empty or different format
                    pass
                
                print(f"✅ Login successful!")
                
                # Get IST time
                ist = pytz.timezone('Asia/Kolkata')
                current_ist = datetime.now(ist)
                
                bot_msg = f"✅ {self.email} online!"
                
                self.send_notification(
                    "Bot Started",
                    bot_msg,
                    priority="default",
                    tags="robot"
                )
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def sync_cooldown_from_server(self):
        """Check server for existing cooldown and sync with local state"""
        try:
            # Check if we can assign task to self
            check_url = f"{self.base_url}/api/tasks/can-assign-task-to-self"
            response = self.session.get(check_url)
            
            if response.status_code == 200:
                data = response.json()
                
                # TaskFlux uses 'default' object for task claim status
                default_data = data.get('default', {})
                
                # Check if we can assign/claim
                can_claim = default_data.get('canAssign', True)
                allowed_after = default_data.get('allowedAfter')
                reason = default_data.get('reason', '')
                
                if not can_claim and allowed_after:
                    # There's an active cooldown - parse the allowedAfter time
                    try:
                        # Parse ISO format: '2025-11-06T12:24:19.254Z'
                        cooldown_end = datetime.fromisoformat(allowed_after.replace('Z', '+00:00'))
                        
                        # Convert to IST (Indian Standard Time)
                        ist = pytz.timezone('Asia/Kolkata')
                        if cooldown_end.tzinfo:
                            cooldown_end_ist = cooldown_end.astimezone(ist)
                            cooldown_end = cooldown_end_ist.replace(tzinfo=None)
                        else:
                            # If no timezone, assume UTC and convert to IST
                            utc = pytz.UTC
                            cooldown_end = utc.localize(cooldown_end).astimezone(ist).replace(tzinfo=None)
                        
                        # Check if this is a new cooldown (not previously tracked)
                        is_new_cooldown = self.cooldown_end is None or abs((self.cooldown_end - cooldown_end).total_seconds()) > 300
                        
                        self.save_cooldown(cooldown_end)
                        
                        remaining = cooldown_end - datetime.now()
                        hours = remaining.total_seconds() / 3600
                        
                        # Send notification for new cooldown
                        if is_new_cooldown:
                            self.send_notification(
                                "Cooldown Active",
                                f"⏰ {hours:.1f} hours remaining\nUntil: {cooldown_end.strftime('%I:%M %p IST')}",
                                priority="default",
                                tags="hourglass"
                            )
                    except Exception as e:
                        print(f"⚠️ Could not parse cooldown time: {e}")
                        print(f"   allowedAfter value: {allowed_after}")
                        # Assume 24h from now if we can't parse
                        cooldown_end = datetime.now() + timedelta(hours=24)
                        self.save_cooldown(cooldown_end)
                        print(f"⏰ Server cooldown detected, estimated end: {cooldown_end.strftime('%I:%M %p IST')}")
                else:
                    # No cooldown on server
                    if self.cooldown_end:
                        if datetime.now() >= self.cooldown_end:
                            # Local cooldown expired, clear it
                            print(f"✅ Cooldown expired, ready to claim!")
                            self.cooldown_end = None
                            self.save_cooldown(None)
                        else:
                            # Server says OK but we have local cooldown that hasn't expired
                            # Trust local cooldown
                            remaining = self.cooldown_end - datetime.now()
                            hours = remaining.total_seconds() / 3600
                            print(f"⏰ Local cooldown: {hours:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
                    else:
                        print(f"✅ No active cooldown - ready to claim!")
            else:
                print(f"⚠️ Could not check server cooldown status (HTTP {response.status_code})")
                        
        except Exception as e:
            print(f"⚠️ Error syncing cooldown: {e}")
    
    def can_claim_task(self):
        """Check if we can claim a task (not in cooldown)"""
        try:
            check_url = f"{self.base_url}/api/tasks/can-assign-task-to-self"
            response = self.session.get(check_url)
            
            if response.status_code == 200:
                data = response.json()
                # Response format might be: {"canClaim": true/false} or similar
                can_claim = data.get('canClaim') or data.get('canAssign') or data.get('allowed', True)
                return can_claim
            else:
                # If endpoint fails, assume we can try
                return True
        except Exception as e:
            print(f"⚠️ Error checking claim status: {e}")
            return True
    
    def get_available_tasks(self):
        """Fetch available tasks from task-pool and filter out assigned ones"""
        try:
            # TaskFlux uses task-pool endpoint for available tasks
            tasks_url = f"{self.base_url}/api/tasks/task-pool"
            
            response = self.session.get(tasks_url)
            
            if response.status_code == 200:
                tasks = response.json()
                # Return tasks array - might be direct array or nested
                all_tasks = tasks if isinstance(tasks, list) else tasks.get('tasks', [])
                
                # Filter out tasks that are already assigned
                available_tasks = []
                for task in all_tasks:
                    status = task.get('status', '').lower()
                    assigned_to = task.get('assignedTo', '')
                    
                    # Include tasks that are available (assignment-pending or unassigned)
                    # Exclude tasks that are assigned (to anyone)
                    if status in ['assignment-pending', 'pending', 'available'] and not assigned_to:
                        # This task is available to claim
                        available_tasks.append(task)
                    elif status == 'assigned' and assigned_to == self.user_id:
                        # This is our assigned task - track it
                        assigned_at = task.get('assignedAt') or task.get('createdAt')
                        assignment_deadline = task.get('assignmentDeadline')
                        
                        if assigned_at and not self.task_claimed_at:
                            try:
                                ist = pytz.timezone('Asia/Kolkata')
                                claimed_time = datetime.fromisoformat(assigned_at.replace('Z', '+00:00'))
                                
                                if claimed_time.tzinfo:
                                    claimed_time_ist = claimed_time.astimezone(ist)
                                    claimed_time = claimed_time_ist.replace(tzinfo=None)
                                else:
                                    utc = pytz.UTC
                                    claimed_time = utc.localize(claimed_time).astimezone(ist).replace(tzinfo=None)
                                
                                # Use assignmentDeadline if available, otherwise calculate 6 hours
                                if assignment_deadline:
                                    deadline_time = datetime.fromisoformat(assignment_deadline.replace('Z', '+00:00'))
                                    if deadline_time.tzinfo:
                                        deadline_time = deadline_time.astimezone(ist).replace(tzinfo=None)
                                else:
                                    deadline_time = claimed_time + timedelta(hours=6)
                                
                                self.task_claimed_at = claimed_time
                                self.task_deadline = deadline_time
                            except Exception as e:
                                pass
                
                return available_tasks
            else:
                print(f"⚠️ Failed to fetch tasks: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"⚠️ Error fetching tasks: {e}")
            return []
    
    def claim_task(self, task_id, task_details=None):
        """Claim a specific task"""
        try:
            print(f"🎯 Attempting to claim task {task_id}...")
            
            # TaskFlux claim endpoint - taskId in URL path
            claim_url = f"{self.base_url}/api/tasks/assign-task-to-self/{task_id}"
            
            response = self.session.put(claim_url)
            
            if response.status_code == 200:
                try:
                    task_data = response.json()
                except:
                    task_data = {}
                    
                print(f"✅ Task claimed successfully!")
                
                # Calculate 6-hour deadline (IST timezone)
                ist = pytz.timezone('Asia/Kolkata')
                claim_time = datetime.now(ist)
                deadline_time = claim_time + timedelta(hours=6)
                
                # Store deadline for tracking
                self.task_claimed_at = claim_time
                self.task_deadline = deadline_time
                self.deadline_warning_sent = False
                self.deadline_final_warning_sent = False
                
                # DON'T start cooldown yet - wait for task completion
                # Just send notification about task assignment
                
                # Build detailed notification message
                task_type = task_data.get('type') or (task_details.get('type') if task_details else 'N/A')
                task_price = task_data.get('price') or (task_details.get('price') if task_details else 'N/A')
                
                # Try to get subreddit and title from various fields
                subreddit = None
                title = None
                submit_url = None
                
                if task_data:
                    subreddit = task_data.get('subreddit') or task_data.get('subredditName')
                    title = task_data.get('title') or task_data.get('postTitle')
                    submit_url = task_data.get('submitUrl') or task_data.get('submissionUrl')
                
                if task_details and not subreddit:
                    subreddit = task_details.get('subreddit') or task_details.get('subredditName')
                    title = task_details.get('title') or task_details.get('postTitle')
                    submit_url = task_details.get('submitUrl') or task_details.get('submissionUrl')
                
                # ═══════════════════════════════════════════════════════════
                # PRINT DETAILED TASK INFO IN TERMINAL
                # ═══════════════════════════════════════════════════════════
                print(f"\n{'═'*60}")
                print(f"🎯 TASK DETAILS")
                print(f"{'═'*60}")
                print(f"📋 Type: {task_type.upper()}")
                print(f"💰 Price: ${task_price}")
                print(f"🆔 Task ID: {task_id}")
                print(f"⏰ Claimed at: {claim_time.strftime('%I:%M:%S %p IST')}")
                print(f"⏰ DEADLINE: {deadline_time.strftime('%I:%M %p IST')} (6 hours)")
                print(f"📅 Date: {deadline_time.strftime('%B %d, %Y')}")
                
                if subreddit:
                    print(f"{'─'*60}")
                    if subreddit.startswith('r/'):
                        print(f"📍 Subreddit: {subreddit}")
                        print(f"🔗 URL: https://www.reddit.com/{subreddit}")
                    else:
                        print(f"📍 Subreddit: r/{subreddit}")
                        print(f"🔗 URL: https://www.reddit.com/r/{subreddit}")
                
                if title:
                    print(f"{'─'*60}")
                    print(f"📝 Post Title:")
                    # Word wrap for long titles
                    if len(title) > 56:
                        words = title.split()
                        line = "   "
                        for word in words:
                            if len(line) + len(word) + 1 > 60:
                                print(line)
                                line = "   " + word
                            else:
                                line += " " + word if line != "   " else word
                        if line != "   ":
                            print(line)
                    else:
                        print(f"   {title}")
                
                print(f"{'─'*60}")
                if submit_url:
                    print(f"🔗 Submit URL:")
                    print(f"   {submit_url}")
                else:
                    print(f"🔗 Submit URL:")
                    print(f"   https://taskflux.net/tasks/{task_id}/submission")
                
                print(f"{'─'*60}")
                print(f"⚠️  WARNING: Complete within 6 hours or lose task!")
                print(f"✅ After completion: 24-hour cooldown starts")
                print(f"{'═'*60}\n")
                
                # Format notification message with DEADLINE
                task_info = f"🎯 {task_type.upper()}\n"
                task_info += f"💰 Price: ${task_price}\n"
                task_info += f"\n⏰ DEADLINE: {deadline_time.strftime('%I:%M %p IST')}\n"
                task_info += f"📅 Complete within 6 hours!\n"
                
                if subreddit:
                    # Format subreddit URL
                    task_info += f"\n📍 "
                    if subreddit.startswith('r/'):
                        task_info += f"Subreddit: https://www.reddit.com/{subreddit}\n"
                    else:
                        task_info += f"Subreddit: https://www.reddit.com/r/{subreddit}\n"
                
                if title:
                    # Truncate long titles
                    display_title = title[:80] + "..." if len(title) > 80 else title
                    task_info += f"📝 Title: {display_title}\n"
                
                if submit_url:
                    task_info += f"\n🔗 Submit: {submit_url}"
                else:
                    task_info += f"\n🔗 Submit: https://taskflux.net/tasks/{task_id}/submission"
                
                task_info += f"\n\n⚠️ URGENT: Complete within 6h or lose task!"
                task_info += f"\n✅ Then cooldown starts (24h)"
                
                # HIGHEST PRIORITY - Task assignment is most critical
                self.send_notification(
                    "🎯 TASK ASSIGNED - 6H LIMIT",
                    task_info,
                    priority="urgent",
                    tags="rotating_light,alarm_clock,warning"
                )
                return True
            else:
                print(f"❌ Failed to claim task: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error claiming task: {e}")
            return False
    
    def submit_task(self, task_id, submission_data):
        """Submit completed task"""
        try:
            print(f"📤 Submitting task {task_id}...")
            
            submit_url = f"{self.base_url}/api/tasks/{task_id}/submission"
            
            response = self.session.post(submit_url, json=submission_data)
            
            if response.status_code == 200:
                print(f"✅ Task submitted!")
                
                # NOW start the 24-hour cooldown after task completion
                cooldown_end = datetime.now() + timedelta(hours=24)
                self.save_cooldown(cooldown_end)
                
                # Get IST time for notification
                ist = pytz.timezone('Asia/Kolkata')
                cooldown_end_ist = cooldown_end.astimezone(ist)
                
                # Clear deadline tracking since task is completed
                self.task_claimed_at = None
                self.task_deadline = None
                self.deadline_warning_sent = False
                self.deadline_final_warning_sent = False
                self.current_task_id = None
                self.current_task_type = None
                
                self.send_notification(
                    "Task Completed",
                    "✅ Task done! Well done!",
                    tags="white_check_mark"
                )
                
                # Send cooldown started notification with detailed info
                cooldown_msg = f"Cooldown: 24.0h\n"
                cooldown_msg += f"Until: {cooldown_end_ist.strftime('%I:%M %p IST')}\n"
                cooldown_msg += f"Date: {cooldown_end_ist.strftime('%m/%d/%y')}\n"
                cooldown_msg += f"\n⏰ Next task available after cooldown"
                
                self.send_notification(
                    "Cooldown Started",
                    cooldown_msg,
                    priority="default",
                    tags="alarm_clock"
                )
                return True
            else:
                print(f"❌ Failed to submit task: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error submitting task: {e}")
            return False
    
    def get_task_summary(self):
        """Fetch task summary to get total amount earned"""
        try:
            summary_url = f"{self.base_url}/api/tasks/task-summary"
            response = self.session.get(summary_url)
            
            if response.status_code == 200:
                data = response.json()
                total_amount = data.get('totalAmount', 0)
                total_payouts = data.get('totalPayouts', 0)
                remaining_payout = data.get('remainingPayout', 0)
                
                return {
                    'totalAmount': total_amount,
                    'totalPayouts': total_payouts,
                    'remainingPayout': remaining_payout
                }
            else:
                print(f"⚠️ Failed to fetch task summary: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"⚠️ Error fetching task summary: {e}")
            return None
    
    def check_task_completion(self):
        """Check if current task has been completed and sync cooldown with server"""
        # Only check if we have an active task
        if not self.task_claimed_at:
            return False
            
        try:
            print(f"🔍 Checking task completion status...")
            
            # First, sync with server to check cooldown status
            # This will tell us if a task was completed (which triggers cooldown)
            self.sync_cooldown_from_server()
            
            # Check if server has started a cooldown (indicates task completion)
            if self.is_in_cooldown():
                # Task was completed - cooldown started
                print(f"✅ Task completed! Cooldown detected from server.")
                
                # Get IST time for notification
                ist = pytz.timezone('Asia/Kolkata')
                
                # Clear deadline tracking since task is completed
                was_tracking = self.task_claimed_at is not None
                self.task_claimed_at = None
                self.task_deadline = None
                self.deadline_warning_sent = False
                self.deadline_final_warning_sent = False
                self.current_task_id = None
                self.current_task_type = None
                
                # Only send notification if we were tracking a task
                if was_tracking:
                    remaining = self.get_cooldown_remaining()
                    hours = remaining.total_seconds() / 3600 if remaining else 0
                    
                    # Fetch task summary to get total amount
                    task_summary = self.get_task_summary()
                    total_amount = task_summary.get('totalAmount', 0) if task_summary else 0
                    
                    # Send task completion notification with total amount
                    completion_msg = f"✅ Task completed! Well done!\n\n"
                    completion_msg += f"💰 Total Amount: ${total_amount}\n"
                    
                    self.send_notification(
                        "Task Completed",
                        completion_msg,
                        priority="high",
                        tags="white_check_mark"
                    )
                    
                    print(f"🎉 Task completion confirmed!")
                    print(f"💰 Total Amount: ${total_amount}")
                    
                    # Send cooldown notification
                    cooldown_msg = f"⏰ Cooldown: {hours:.1f}h\n"
                    cooldown_msg += f"Until: {self.cooldown_end.strftime('%I:%M %p IST')}\n"
                    cooldown_msg += f"Date: {self.cooldown_end.strftime('%m/%d/%y')}\n"
                    cooldown_msg += f"\n⏰ Next task available after cooldown"
                    
                    self.send_notification(
                        "Cooldown Started",
                        cooldown_msg,
                        priority="default",
                        tags="alarm_clock,hourglass"
                    )
                    
                    print(f"⏰ Cooldown: {hours:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
                
                return True
            
            # Alternative: Check task status via API endpoint if available
            # This is a fallback in case TaskFlux has a direct task status endpoint
            status_url = f"{self.base_url}/api/tasks/my-tasks"  # or /api/tasks/assigned
            
            response = self.session.get(status_url)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if there are any assigned/active tasks
                # If no active tasks and we were tracking one, it might be completed
                tasks = data if isinstance(data, list) else data.get('tasks', [])
                
                if not tasks and self.task_claimed_at:
                    # No active tasks but we had one - might be completed
                    print(f"⚠️ No active tasks found - task may have been completed")
                    
                    # Sync again to be sure
                    self.sync_cooldown_from_server()
                    
                    if self.is_in_cooldown():
                        print(f"✅ Confirmed: Task completed and cooldown started")
                        
                        # Fetch task summary to get total amount
                        task_summary = self.get_task_summary()
                        total_amount = task_summary.get('totalAmount', 0) if task_summary else 0
                        
                        # Send task completion notification with total amount
                        completion_msg = f"✅ Task completed! Well done!\n\n"
                        completion_msg += f"💰 Total Amount: ${total_amount}\n"
                        
                        self.send_notification(
                            "Task Completed",
                            completion_msg,
                            priority="high",
                            tags="party_popper,white_check_mark,money_bag"
                        )
                        
                        print(f"💰 Total Amount: ${total_amount}")
                        
                        # Send cooldown notification
                        remaining = self.get_cooldown_remaining()
                        hours = remaining.total_seconds() / 3600 if remaining else 0
                        
                        cooldown_msg = f"⏰ Cooldown: {hours:.1f}h\n"
                        cooldown_msg += f"Until: {self.cooldown_end.strftime('%I:%M %p IST')}\n"
                        cooldown_msg += f"Date: {self.cooldown_end.strftime('%m/%d/%y')}\n"
                        cooldown_msg += f"\n⏰ Next task available after cooldown"
                        
                        self.send_notification(
                            "Cooldown Started",
                            cooldown_msg,
                            priority="default",
                            tags="alarm_clock,hourglass"
                        )
                        
                        # Clear deadline tracking
                        self.task_claimed_at = None
                        self.task_deadline = None
                        self.deadline_warning_sent = False
                        self.deadline_final_warning_sent = False
                        self.current_task_id = None
                        self.current_task_type = None
                        
                        return True
                    
        except Exception as e:
            print(f"⚠️ Error checking task completion: {e}")
            
        return False
    
    def check_task_deadline(self):
        """Check if task deadline is approaching and send warnings"""
        if not self.task_deadline:
            return  # No active task
        
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Make sure both are timezone-aware for comparison
        if self.task_deadline.tzinfo is None:
            task_deadline = ist.localize(self.task_deadline)
        else:
            task_deadline = self.task_deadline
        
        time_remaining = task_deadline - now
        hours_remaining = time_remaining.total_seconds() / 3600
        
        # Check if deadline has passed
        if hours_remaining <= 0:
            print(f"❌ DEADLINE PASSED! Task may be lost!")
            print(f"🔄 Syncing with server to check cooldown status...")
            
            # Sync with server to get the actual cooldown
            self.sync_cooldown_from_server()
            
            # Send warning notification about missed deadline
            self.send_notification(
                "⚠️ DEADLINE EXCEEDED",
                f"❌ Task deadline passed!\n"
                f"Time: {now.strftime('%I:%M %p IST')}\n"
                f"Deadline was: {task_deadline.strftime('%I:%M %p IST')}\n\n"
                f"⏰ Task lost - Cooldown may have started!\n"
                f"Syncing with server...",
                priority="urgent",
                tags="x,warning,rotating_light"
            )
            
            # If server didn't start cooldown, start it locally (24 hours)
            if not self.is_in_cooldown():
                print(f"⏰ Server hasn't started cooldown - starting 24h cooldown locally")
                cooldown_end = datetime.now() + timedelta(hours=24)
                self.save_cooldown(cooldown_end)
                
                # Get IST time for notification
                ist_tz = pytz.timezone('Asia/Kolkata')
                cooldown_end_ist = ist_tz.localize(cooldown_end) if cooldown_end.tzinfo is None else cooldown_end.astimezone(ist_tz)
                
                # Send cooldown started notification
                cooldown_msg = f"⏰ Cooldown: 24.0h\n"
                cooldown_msg += f"Until: {cooldown_end_ist.strftime('%I:%M %p IST')}\n"
                cooldown_msg += f"Date: {cooldown_end_ist.strftime('%m/%d/%y')}\n"
                cooldown_msg += f"\n❌ Reason: Task deadline exceeded\n"
                cooldown_msg += f"⏰ Next task available after cooldown"
                
                self.send_notification(
                    "Cooldown Started (Deadline Missed)",
                    cooldown_msg,
                    priority="high",
                    tags="alarm_clock,warning"
                )
            else:
                # Server already started cooldown
                remaining = self.get_cooldown_remaining()
                hours_cd = remaining.total_seconds() / 3600 if remaining else 0
                print(f"✅ Server cooldown active: {hours_cd:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
            
            # Clear deadline tracking
            self.task_claimed_at = None
            self.task_deadline = None
            self.deadline_warning_sent = False
            self.deadline_final_warning_sent = False
            self.current_task_id = None
            self.current_task_type = None
            return
        
        # Send warning at 2 hours remaining
        if hours_remaining <= 2 and not self.deadline_warning_sent:
            print(f"⚠️ Task deadline approaching: {hours_remaining:.1f}h remaining")
            self.send_notification(
                "⚠️ 2 HOURS LEFT",
                f"⏰ Only {hours_remaining:.1f}h to complete task!\n"
                f"Deadline: {task_deadline.strftime('%I:%M %p IST')}\n\n"
                f"Complete task soon or it will be lost!",
                priority="high",
                tags="warning,alarm_clock"
            )
            self.deadline_warning_sent = True
        
        # Send final warning at 30 minutes remaining
        elif hours_remaining <= 0.5 and not self.deadline_final_warning_sent:
            minutes_remaining = hours_remaining * 60
            print(f"🚨 URGENT: Task deadline in {minutes_remaining:.0f} minutes!")
            self.send_notification(
                "🚨 30 MINUTES LEFT",
                f"🚨 URGENT: Only {minutes_remaining:.0f} minutes left!\n"
                f"Deadline: {task_deadline.strftime('%I:%M %p IST')}\n\n"
                f"COMPLETE TASK NOW OR LOSE IT!",
                priority="urgent",
                tags="rotating_light,warning"
            )
            self.deadline_final_warning_sent = True
    
    def check_for_assigned_task_on_server(self):
        """Check if there's an assigned task on the server"""
        try:
            # Method 1: Check can-assign-task-to-self endpoint (fastest)
            check_url = f"{self.base_url}/api/tasks/can-assign-task-to-self"
            response = self.session.get(check_url)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check the 'default' object for task assignment status
                default_data = data.get('default', {})
                can_assign = default_data.get('canAssign', True)
                reason = default_data.get('reason', '')
                
                # If canAssign is False, check if it's because of an assigned task
                if not can_assign:
                    # Check if the reason indicates an assigned task
                    if 'assigned task' in reason.lower() or 'complete it before' in reason.lower():
                        return True
            
            # Method 2: Check task-pool for tasks assigned to us (most reliable)
            tasks_url = f"{self.base_url}/api/tasks/task-pool"
            pool_response = self.session.get(tasks_url)
            
            if pool_response.status_code == 200:
                pool_data = pool_response.json()
                all_tasks = pool_data if isinstance(pool_data, list) else pool_data.get('tasks', [])
                
                # Check if any task is assigned to us
                for task in all_tasks:
                    status = task.get('status', '').lower()
                    assigned_to = task.get('assignedTo', '')
                    
                    if status == 'assigned' and assigned_to == self.user_id:
                        return True
                    
            return False
            
        except Exception as e:
            # If we can't check, assume no assigned task
            return False
    
    def check_for_running_task(self):
        """Check if there's a running/assigned task on the server"""
        try:
            # Use task-pool endpoint to get actual task details
            # task-summary only has statistics (completed count, payout numbers)
            tasks_url = f"{self.base_url}/api/tasks/task-pool"
            response = self.session.get(tasks_url)
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            all_tasks = data if isinstance(data, list) else data.get('tasks', [])
            
            # Filter for tasks assigned to us
            assigned_tasks = []
            for task in all_tasks:
                status = task.get('status', '').lower()
                assigned_to = task.get('assignedTo', '')
                
                # Check if this task is assigned to us
                if status == 'assigned' and assigned_to == self.user_id:
                    assigned_tasks.append(task)
            
            if not assigned_tasks:
                return False
            
            # Found assigned task(s)
            print(f"⚠️ Found {len(assigned_tasks)} assigned task(s) on server!")
            
            # Get the first assigned task
            task = assigned_tasks[0]
            task_id = task.get('_id') or task.get('id') or task.get('taskId', 'unknown')
            task_type = task.get('type', 'N/A')
            task_price = task.get('microWorkerPrice') or task.get('price', 'N/A')
            assigned_at = task.get('assignedAt') or task.get('createdAt')
            assignment_deadline = task.get('assignmentDeadline')
            
            # Calculate deadline
            ist = pytz.timezone('Asia/Kolkata')
            if assigned_at:
                try:
                    # Parse ISO format
                    claimed_time = datetime.fromisoformat(assigned_at.replace('Z', '+00:00'))
                    
                    # Convert to IST
                    if claimed_time.tzinfo:
                        claimed_time_ist = claimed_time.astimezone(ist)
                        claimed_time = claimed_time_ist.replace(tzinfo=None)
                    else:
                        utc = pytz.UTC
                        claimed_time = utc.localize(claimed_time).astimezone(ist).replace(tzinfo=None)
                    
                    # Use assignmentDeadline if available, otherwise calculate 6 hours
                    if assignment_deadline:
                        deadline_time = datetime.fromisoformat(assignment_deadline.replace('Z', '+00:00'))
                        if deadline_time.tzinfo:
                            deadline_time = deadline_time.astimezone(ist).replace(tzinfo=None)
                    else:
                        deadline_time = claimed_time + timedelta(hours=6)
                    
                    # Store deadline tracking
                    self.task_claimed_at = claimed_time
                    self.task_deadline = deadline_time
                    self.deadline_warning_sent = False
                    self.deadline_final_warning_sent = False
                    
                    # Store current task ID and type for status tracking
                    self.current_task_id = task_id
                    self.current_task_type = task_type
                    
                    # Calculate time remaining
                    time_remaining = deadline_time - datetime.now()
                    hours_remaining = time_remaining.total_seconds() / 3600
                    
                    print(f"\n{'═'*60}")
                    print(f"⚠️ ASSIGNED TASK DETECTED")
                    print(f"{'═'*60}")
                    print(f"📋 Type: {task_type}")
                    print(f"💰 Price: ${task_price}")
                    print(f"🆔 Task ID: {task_id}")
                    print(f"⏰ Assigned at: {claimed_time.strftime('%I:%M:%S %p IST')}")
                    print(f"⏰ DEADLINE: {deadline_time.strftime('%I:%M %p IST')}")
                    print(f"⏳ Time remaining: {hours_remaining:.1f}h")
                    print(f"{'═'*60}\n")
                    
                    # Send notification
                    if hours_remaining > 0:
                        self.send_notification(
                            "⚠️ Assigned Task Found",
                            f"🎯 {task_type}\n"
                            f"💰 Price: ${task_price}\n\n"
                            f"⏰ DEADLINE: {deadline_time.strftime('%I:%M %p IST')}\n"
                            f"⏳ Remaining: {hours_remaining:.1f}h\n\n"
                            f"⚠️ Complete before deadline!",
                            priority="urgent",
                            tags="warning,alarm_clock"
                        )
                    else:
                        # Deadline already passed
                        self.send_notification(
                            "⚠️ Task Deadline Passed",
                            f"❌ Assigned task found but deadline passed!\n"
                            f"🎯 {task_type}\n"
                            f"💰 Price: ${task_price}\n\n"
                            f"Deadline was: {deadline_time.strftime('%I:%M %p IST')}\n"
                            f"⚠️ Cooldown may start soon",
                            priority="urgent",
                            tags="x,warning"
                        )
                        
                except Exception as e:
                    print(f"⚠️ Could not parse task assignment time: {e}")
                    print(f"   Raw time value: {assigned_at}")
            else:
                # No timestamp available, just notify about the task
                print(f"⚠️ Assigned task found (ID: {task_id}) but no timestamp available")
                
                # Store task ID and type for status tracking
                self.current_task_id = task_id
                self.current_task_type = task_type
                
                self.send_notification(
                    "⚠️ Assigned Task Found",
                    f"🎯 {task_type}\n"
                    f"💰 Price: ${task_price}\n"
                    f"🆔 ID: {task_id}\n\n"
                    f"⚠️ Complete this task!",
                    priority="high",
                    tags="warning,alarm_clock"
                )
            
            return True
                
        except Exception as e:
            print(f"⚠️ Error checking for assigned task: {e}")
            return False
    
    def check_task_status_by_id(self, task_id, task_type):
        """
        Check if a specific task has been completed by checking its status
        Uses the task tracking API to check if status changed to 'published'
        Returns: (is_completed: bool, task_details: dict or None)
        """
        try:
            # Determine which API endpoint to use based on task type
            if 'comment' in task_type.lower():
                api_url = f"{self.base_url}/api/tasks/?filters%5Btype%5D=RedditCommentTask&filters%5Bstatus%5D=all&pageNum=1"
            elif 'reply' in task_type.lower():
                api_url = f"{self.base_url}/api/tasks/?filters%5Btype%5D=RedditReplyTask&filters%5Bstatus%5D=all&pageNum=1"
            else:
                print(f"⚠️ Unknown task type: {task_type}")
                return False, None
            
            response = self.session.get(api_url)
            
            if response.status_code != 200:
                print(f"⚠️ Failed to fetch task status: {response.status_code}")
                return False, None
            
            data = response.json()
            tasks = data.get('tasks', [])
            
            # Find our task by ID
            for task in tasks:
                if task.get('_id') == task_id:
                    status = task.get('status', '').lower()
                    
                    if status == 'published':
                        # Task completed!
                        print(f"✅ Task {task_id} status: PUBLISHED (completed)")
                        return True, task
                    else:
                        print(f"⏳ Task {task_id} status: {status.upper()}")
                        return False, task
            
            # Task not found in the list
            print(f"⚠️ Task {task_id} not found in tracking API")
            return False, None
                
        except Exception as e:
            print(f"⚠️ Error checking task status: {e}")
            return False, None
    
    def is_within_claiming_hours(self):
        """Check if current time is within allowed claiming hours (8 AM - 11 PM IST)"""
        try:
            # Get current time in Indian timezone
            ist = pytz.timezone('Asia/Kolkata')
            now_ist = datetime.now(ist)
            current_hour = now_ist.hour
            
            # Allowed hours: 8 AM (8) to 11 PM (23)
            if 8 <= current_hour <= 23:
                return True
            else:
                print(f"⏰ Outside claiming hours (8 AM - 11 PM IST). Current time: {now_ist.strftime('%I:%M %p IST')}")
                return False
        except Exception as e:
            print(f"⚠️ Error checking time: {e}")
            return True  # Default to allowing claims if error
    
    def is_content_safe(self, content):
        """
        Check if task content is safe and unlikely to be removed by AutoMod or moderators
        Returns: (is_safe: bool, reason: str)
        """
        if not content:
            return True, "No content to check"
        
        content_lower = content.lower()
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if pattern.lower() in content_lower:
                return False, f"Contains suspicious pattern: '{pattern}'"
        
        # Check for excessive caps (>50% of letters are uppercase)
        letters = [c for c in content if c.isalpha()]
        if letters:
            caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if caps_ratio > 0.5 and len(letters) > 10:
                return False, "Excessive uppercase (possible spam)"
        
        # Check for excessive punctuation/special chars
        special_chars = sum(1 for c in content if c in '!?$#@*')
        if len(content) > 0:
            special_ratio = special_chars / len(content)
            if special_ratio > 0.2:
                return False, "Excessive special characters"
        
        # Check for excessive emojis (simple check for common emoji patterns)
        emoji_count = content.count('🔥') + content.count('💰') + content.count('💵') + content.count('🚀')
        if emoji_count > 3:
            return False, "Excessive promotional emojis"
        
        # Check for very short low-effort comments (less than 10 chars)
        if len(content.strip()) < 10:
            return False, "Comment too short (likely low-effort)"
        
        # Check for repetitive characters (like "hahahaha" or "!!!!!")
        for char in set(content):
            if content.count(char * 5) > 0:  # 5 or more of the same char in a row
                return False, f"Repetitive characters detected: '{char * 5}'"
        
        return True, "Content appears safe"
    
    def check_and_claim_tasks(self):
        """Check for available tasks and claim if not in cooldown"""
        # First, check if we already have an assigned task on the server
        if self.check_for_assigned_task_on_server():
            # Task is assigned - don't check for new tasks
            if self.task_deadline:
                time_remaining = self.task_deadline - datetime.now()
                hours_remaining = time_remaining.total_seconds() / 3600
                
                if hours_remaining > 0:
                    # Task still active, skip checking for new tasks
                    return False
            
            # No local deadline tracking, skip anyway
            return False
        
        # Also check local task tracking (fallback)
        if self.task_claimed_at or self.task_deadline:
            # We have local tracking of a task
            time_remaining = self.task_deadline - datetime.now() if self.task_deadline else timedelta(0)
            hours_remaining = time_remaining.total_seconds() / 3600
            
            if hours_remaining > 0:
                # Task still active, skip checking for new tasks
                return False
            else:
                # Deadline passed, clear tracking
                self.task_claimed_at = None
                self.task_deadline = None
                self.current_task_id = None
                self.current_task_type = None
        
        # Sync cooldown status from server first
        self.sync_cooldown_from_server()
        
        # Cooldown already checked in main loop, but check again after server sync
        if self.is_in_cooldown():
            remaining = self.get_cooldown_remaining()
            hours = remaining.total_seconds() / 3600
            print(f"⏳ Server sync updated cooldown: {hours:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
            return False
        
        # Check if within allowed claiming hours (8 AM - 11 PM IST)
        if not self.is_within_claiming_hours():
            return False
        
        print(f"🔍 Checking for available tasks...")
        tasks = self.get_available_tasks()
        
        if not tasks:
            self.consecutive_empty_checks += 1
            print(f"📭 No tasks available at the moment (empty check #{self.consecutive_empty_checks})")
            
            # Adaptive interval: slow down checks when no tasks are available
            if self.consecutive_empty_checks >= 3:
                # Keep interval at 3 seconds (no adaptation)
                self.current_check_interval = 3
                print(f"⏱️ Check interval: {self.current_check_interval}s")
            
            return False
        
        # Tasks found - reset counters and speed up checks
        if self.consecutive_empty_checks > 0:
            print(f"✨ Tasks appeared after {self.consecutive_empty_checks} empty checks!")
        self.consecutive_empty_checks = 0
        self.current_check_interval = self.min_check_interval
        self.last_task_seen = datetime.now()
        self.tasks_seen_today += len(tasks)
        
        print(f"📋 Found {len(tasks)} task(s) available")
        
        # ═══════════════════════════════════════════════════════════
        # DISPLAY ALL AVAILABLE TASKS IN TERMINAL
        # ═══════════════════════════════════════════════════════════
        print(f"\n{'═'*80}")
        print(f"📋 AVAILABLE TASKS ({len(tasks)} total)")
        print(f"{'═'*80}")
        
        # Send notification for available tasks - HIGH priority
        if len(tasks) > 0:
            self.send_notification(
                "Tasks Available",
                f"📋 {len(tasks)} task{'s' if len(tasks) != 1 else ''} found",
                priority="high",
                tags="inbox_tray,bell"
            )
        
        for idx, task in enumerate(tasks, 1):
            task_id = task.get('_id') or task.get('id') or task.get('taskId', 'unknown')
            task_type = task.get('type', 'N/A')
            task_price = task.get('microWorkerPrice') or task.get('price', '2.00')
            task_name = task.get('name', '')
            task_title = task.get('title', '')
            subreddit = task.get('subreddit') or task.get('subredditName', '')
            content = task.get('content', '') or task.get('comment', '') or task.get('text', '') or task.get('body', '')
            
            print(f"\n{'─'*80}")
            print(f"Task #{idx}")
            print(f"{'─'*80}")
            print(f"📝 Type: {task_type}")
            print(f"💰 Price: ${task_price}")
            
            if subreddit:
                if subreddit.startswith('r/'):
                    print(f"📍 Subreddit: {subreddit}")
                else:
                    print(f"📍 Subreddit: r/{subreddit}")
            
            if task_title:
                print(f"📄 Title:")
                # Word wrap long titles
                if len(task_title) > 70:
                    words = task_title.split()
                    line = "   "
                    for word in words:
                        if len(line) + len(word) + 1 > 76:
                            print(line)
                            line = "   " + word
                        else:
                            line += (" " + word) if line != "   " else word
                    if line != "   ":
                        print(line)
                else:
                    print(f"   {task_title}")
            
            if content:
                content_preview = content[:100].replace('\n', ' ').strip()
                if len(content) > 100:
                    content_preview += "..."
                print(f"💬 Content: \"{content_preview}\"")
        
        print(f"\n{'═'*80}\n")
        
        # Filter tasks - only claim "RedditCommentTask", "RedditReplyToComment", and "RedditReplyTask"
        allowed_task_types = ['redditcommenttask','redditreplytask']
        claimable_tasks = []
        rejected_tasks = []
        
        for task in tasks:
            task_type = task.get('type', '').lower()
            task_name = task.get('name', '').lower()
            task_title = task.get('title', '').lower()
            task_id = task.get('_id') or task.get('id') or task.get('taskId', 'unknown')
            
            # Check if task type matches allowed types
            type_matches = any(allowed_type in task_type or allowed_type in task_name or allowed_type in task_title 
                   for allowed_type in allowed_task_types)
            
            if type_matches:
                # Check task content for safety
                content = task.get('content', '') or task.get('comment', '') or task.get('text', '') or task.get('body', '')
                is_safe, reason = self.is_content_safe(content)
                
                if is_safe:
                    claimable_tasks.append(task)
                else:
                    rejected_tasks.append({
                        'task': task,
                        'reason': f"Unsafe content - {reason}",
                        'content': content
                    })
            else:
                # Task type not allowed
                rejected_tasks.append({
                    'task': task,
                    'reason': f"Wrong type - only 'RedditCommentTask', 'RedditReplyToComment', and 'RedditReplyTask' allowed",
                    'content': None
                })
        
        # ═══════════════════════════════════════════════════════════
        # DISPLAY TASK FILTERING RESULTS
        # ═══════════════════════════════════════════════════════════
        print(f"\n{'─'*70}")
        print(f"📊 TASK FILTERING RESULTS")
        print(f"{'─'*70}")
        print(f"✅ Claimable tasks: {len(claimable_tasks)}")
        print(f"🚫 Rejected tasks: {len(rejected_tasks)}")
        print(f"{'─'*70}")
        
        # Show rejected tasks with reasons
        if rejected_tasks:
            print(f"\n{'═'*80}")
            print(f"🚫 REJECTED TASKS ({len(rejected_tasks)} task{'s' if len(rejected_tasks) != 1 else ''})")
            print(f"{'═'*80}")
            
            # Send notification for rejected tasks - LOW priority (informational)
            self.send_notification(
                "Rejected Tasks",
                f"🚫 {len(rejected_tasks)} task{'s' if len(rejected_tasks) != 1 else ''} rejected",
                priority="low",
                tags="no_entry_sign"
            )
            
            for idx, rejected in enumerate(rejected_tasks, 1):
                task = rejected['task']
                reason = rejected['reason']
                content = rejected['content']
                
                task_id = task.get('_id') or task.get('id') or task.get('taskId', 'unknown')
                task_type = task.get('type', 'N/A')
                task_price = task.get('microWorkerPrice') or task.get('price', '2.00')
                task_name = task.get('name', '')
                task_title = task.get('title', '')
                subreddit = task.get('subreddit') or task.get('subredditName', '')
                
                print(f"\n{'─'*80}")
                print(f"Rejected Task #{idx}")
                print(f"{'─'*80}")
                print(f"📝 Type: {task_type}")
                print(f"💰 Price: ${task_price}")
                print(f"❌ Rejection Reason: {reason}")
                
                if subreddit:
                    if subreddit.startswith('r/'):
                        print(f"📍 Subreddit: {subreddit}")
                    else:
                        print(f"📍 Subreddit: r/{subreddit}")
                
                if task_title:
                    print(f"📄 Title:")
                    # Word wrap long titles
                    if len(task_title) > 70:
                        words = task_title.split()
                        line = "   "
                        for word in words:
                            if len(line) + len(word) + 1 > 76:
                                print(line)
                                line = "   " + word
                            else:
                                line += (" " + word) if line != "   " else word
                        if line != "   ":
                            print(line)
                    else:
                        print(f"   {task_title}")
                
                if content:
                    content_preview = content[:100].replace('\n', ' ').strip()
                    if len(content) > 100:
                        content_preview += "..."
                    print(f"💬 Content: \"{content_preview}\"")
            
            print(f"\n{'═'*80}")
        
        # Show claimable tasks
        if claimable_tasks:
            print(f"\n{'═'*80}")
            print(f"✅ CLAIMABLE TASKS ({len(claimable_tasks)} task{'s' if len(claimable_tasks) != 1 else ''})")
            print(f"{'═'*80}")
            
            # Send notification for claimable tasks - HIGH priority (ready to claim)
            self.send_notification(
                "Claimable Tasks",
                f"✅ {len(claimable_tasks)} safe task{'s' if len(claimable_tasks) != 1 else ''}",
                priority="high",
                tags="white_check_mark,bell"
            )
            
            for idx, task in enumerate(claimable_tasks, 1):
                task_id = task.get('_id') or task.get('id') or task.get('taskId', 'unknown')
                task_type = task.get('type', 'N/A')
                task_price = task.get('microWorkerPrice') or task.get('price', '2.00')
                task_name = task.get('name', '')
                task_title = task.get('title', '')
                subreddit = task.get('subreddit') or task.get('subredditName', '')
                content = task.get('content', '') or task.get('comment', '') or task.get('text', '') or task.get('body', '')
                
                print(f"\n{'─'*80}")
                print(f"Claimable Task #{idx}")
                print(f"{'─'*80}")
                print(f"📝 Type: {task_type}")
                print(f"💰 Price: ${task_price}")
                print(f"✅ Status: SAFE TO CLAIM")
                
                if subreddit:
                    if subreddit.startswith('r/'):
                        print(f"📍 Subreddit: {subreddit}")
                    else:
                        print(f"📍 Subreddit: r/{subreddit}")
                
                if task_title:
                    print(f"📄 Title:")
                    # Word wrap long titles
                    if len(task_title) > 70:
                        words = task_title.split()
                        line = "   "
                        for word in words:
                            if len(line) + len(word) + 1 > 76:
                                print(line)
                                line = "   " + word
                            else:
                                line += (" " + word) if line != "   " else word
                        if line != "   ":
                            print(line)
                    else:
                        print(f"   {task_title}")
                
                if content:
                    content_preview = content[:100].replace('\n', ' ').strip()
                    if len(content) > 100:
                        content_preview += "..."
                    print(f"💬 Content: \"{content_preview}\"")
            
            print(f"\n{'═'*80}\n")
        
        if not claimable_tasks:
            print(f"\n⚠️ No safe claimable tasks found!")
            print(f"   Only 'RedditCommentTask', 'RedditReplyToComment', and 'RedditReplyTask' tasks with safe content are allowed.")
            print(f"{'═'*70}\n")
            return False
        
        print(f"✅ Found {len(claimable_tasks)} safe claimable task(s)")
        print(f"🎯 Claiming the first safe task...")
        
        # Claim the first claimable task
        task = claimable_tasks[0]
        task_id = task.get('_id') or task.get('id') or task.get('taskId')
        task_type = task.get('type', 'N/A')
        
        if task_id:
            # Pass the full task object for better notifications
            return self.claim_task(task_id, task_details=task)
        else:
            return False
    
    def run(self, check_interval=3):
        """
        Main bot loop - fixed 3 second checking interval
        check_interval: seconds between checks (default 3 seconds)
        """
        # Set intervals to 3 seconds
        self.min_check_interval = 3
        self.max_check_interval = 3
        
        self.current_check_interval = 3
        
        # Initial login
        if not self.login():
            print("❌ Failed to login. Exiting...")
            return
        
        # Start monitoring loop directly - initial check happens in first loop iteration
        loop_count = 0
        
        try:
            while True:
                try:
                    loop_count += 1
                    current_time = datetime.now().strftime('%I:%M:%S %p')
                    
                    print(f"\n{'='*60}")
                    print(f"🔄 MONITORING CHECK #{loop_count} - {current_time}")
                    print(f"{'='*60}")
                    
                    # Show statistics
                    if self.last_task_seen:
                        time_since = datetime.now() - self.last_task_seen
                        hours = time_since.total_seconds() / 3600
                        print(f"📊 Stats: Last task {hours:.1f}h ago | Tasks today: {self.tasks_seen_today}")
                    
                    # FLOW: 1. Check for assigned task on server
                    print(f"\n📋 Step 1: Checking for assigned task...")
                    has_assigned_task = self.check_for_assigned_task_on_server()
                    
                    if has_assigned_task:
                        # Task is assigned - monitor it and skip everything else
                        if self.task_deadline:
                            time_remaining = self.task_deadline - datetime.now()
                            hours_remaining = time_remaining.total_seconds() / 3600
                            
                            if hours_remaining > 0:
                                print(f"   ⚠️  Task assigned: {hours_remaining:.1f}h remaining to complete")
                                print(f"   ⏭️  Skipping cooldown & task pool checks")
                                print(f"{'='*60}")
                                
                                # Send notification on first check only with full task details
                                if loop_count == 1:
                                    self.check_for_running_task()  # Get full task details and send notification
                                
                                # Check task deadline and send warnings if needed
                                self.check_task_deadline()
                                
                                # Check if task was completed (checks every 1 minute)
                                self.check_task_completion()
                                
                                # Sleep for 1 minute to check task completion frequently
                                sleep_time = 60  # 1 minute
                                print(f"💤 Sleeping for {sleep_time}s (1 minute) to check task completion...")
                                
                                next_check = datetime.now() + timedelta(seconds=sleep_time)
                                print(f"⏰ Next check: #{loop_count + 1} at {next_check.strftime('%I:%M %p')}")
                                
                                time.sleep(sleep_time)
                                continue
                        else:
                            print(f"   ⚠️  Task assigned on server")
                            print(f"{'='*60}")
                            
                            # Send notification on first check only with full task details
                            if loop_count == 1:
                                self.check_for_running_task()  # Get full task details and send notification
                            
                            # Check task status every 2 minutes to detect completion
                            if self.current_task_id and self.current_task_type:
                                print(f"🔍 Checking task status (ID: {self.current_task_id})...")
                                is_completed, task_details = self.check_task_status_by_id(
                                    self.current_task_id, 
                                    self.current_task_type
                                )
                                
                                if is_completed and task_details:
                                    # Task status changed to "published" - task completed!
                                    print(f"✅ Task {self.current_task_id} completed! Status: PUBLISHED")
                                    
                                    # Extract task details for notification
                                    task_type = task_details.get('taskType', self.current_task_type)
                                    task_price = task_details.get('microWorkerPrice') or task_details.get('randomCommentsPrice', 'N/A')
                                    subreddit = task_details.get('subreddit', '')
                                    project_name = ''
                                    if task_details.get('project'):
                                        project_name = task_details['project'].get('name', '')
                                    
                                    # Fetch task summary to get total amount
                                    task_summary = self.get_task_summary()
                                    total_amount = task_summary.get('totalAmount', 0) if task_summary else 0
                                    
                                    # Send task completion notification FIRST with details
                                    completion_msg = f"✅ Task completed! Well done!\n\n"
                                    completion_msg += f"🎯 Type: {task_type.upper()}\n"
                                    completion_msg += f"💰 Task Price: ${task_price}\n"
                                    
                                    if subreddit:
                                        completion_msg += f"📍 Subreddit: r/{subreddit}\n"
                                    
                                    if project_name:
                                        completion_msg += f"📂 Project: {project_name}\n"
                                    
                                    completion_msg += f"\n💰 Total Earned: ${total_amount}\n"
                                    
                                    self.send_notification(
                                        "Task Completed",
                                        completion_msg,
                                        priority="high",
                                        tags="party_popper,white_check_mark,money_bag"
                                    )
                                    
                                    print(f"🎉 Task completion confirmed!")
                                    print(f"💰 Task Price: ${task_price}")
                                    print(f"💰 Total Amount Earned: ${total_amount}")
                                    
                                    # Wait 2 seconds before checking cooldown
                                    time.sleep(2)
                                    
                                    # Now check for cooldown
                                    print(f"🔍 Checking for cooldown after task completion...")
                                    self.sync_cooldown_from_server()
                                    
                                    if self.is_in_cooldown():
                                        remaining = self.get_cooldown_remaining()
                                        hours = remaining.total_seconds() / 3600 if remaining else 0
                                        
                                        # Send cooldown notification SECOND
                                        cooldown_msg = f"⏰ Cooldown: {hours:.1f}h\n"
                                        cooldown_msg += f"Until: {self.cooldown_end.strftime('%I:%M %p IST')}\n"
                                        cooldown_msg += f"Date: {self.cooldown_end.strftime('%m/%d/%y')}\n"
                                        cooldown_msg += f"\n⏰ Next task available after cooldown"
                                        
                                        self.send_notification(
                                            "Cooldown Started",
                                            cooldown_msg,
                                            priority="default",
                                            tags="alarm_clock,hourglass"
                                        )
                                        
                                        print(f"⏰ Cooldown: {hours:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
                                    
                                    # Clear task tracking
                                    self.task_claimed_at = None
                                    self.task_deadline = None
                                    self.deadline_warning_sent = False
                                    self.deadline_final_warning_sent = False
                                    self.current_task_id = None
                                    self.current_task_type = None
                                    
                                    # Continue to next iteration (will enter cooldown monitoring)
                                    continue
                                else:
                                    print(f"⏳ Task still in progress (not published yet)")
                            else:
                                print(f"⚠️ No task ID stored - cannot check status")
                            
                            # Task still assigned, not completed yet - check again in 2 minutes
                            sleep_time = 120  # 2 minutes
                            print(f"💤 Sleeping for {sleep_time}s (2 minutes) to check task status again...")
                            
                            next_check = datetime.now() + timedelta(seconds=sleep_time)
                            print(f"⏰ Next check: #{loop_count + 1} at {next_check.strftime('%I:%M %p')}")
                            
                            time.sleep(sleep_time)
                            continue
                    
                    # FLOW: 2. Check for cooldown on server
                    print(f"   ✅ No task assigned")
                    print(f"\n⏰ Step 2: Checking cooldown status...")
                    
                    # Sync cooldown from server
                    server_cooldown = self.sync_cooldown_from_server()
                    
                    if server_cooldown:
                        # Server has cooldown - update local state
                        print(f"   ⏳ Server cooldown detected - syncing local state")
                        self.is_in_cooldown()  # This will update from synced cooldown_end
                    
                    # Check local cooldown (now synced with server)
                    if self.is_in_cooldown():
                        remaining = self.get_cooldown_remaining()
                        hours = remaining.total_seconds() / 3600
                        minutes = remaining.total_seconds() / 60
                        print(f"   ⏳ Cooldown active: {hours:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
                        print(f"   ⏭️  Skipping task pool check")
                        print(f"{'='*60}")
                        
                        # Send notification on first check only
                        if loop_count == 1:
                            # Check if cooldown just started (less than 30 minutes elapsed)
                            # This indicates a task was recently completed
                            cooldown_duration = timedelta(hours=24) - remaining
                            cooldown_elapsed_minutes = cooldown_duration.total_seconds() / 60
                            
                            if cooldown_elapsed_minutes < 30:
                                # Task was recently completed! Send completion notification first
                                print(f"🎉 Recent task completion detected ({cooldown_elapsed_minutes:.1f} minutes ago)")
                                
                                # Fetch task summary to get total amount
                                task_summary = self.get_task_summary()
                                total_amount = task_summary.get('totalAmount', 0) if task_summary else 0
                                
                                # Send task completion notification
                                completion_msg = f"⚡Well done!\n\n"
                                completion_msg += f"💰 Total Amount: ${total_amount}\n"
                                
                                self.send_notification(
                                    "Task Completed",
                                    completion_msg,
                                    priority="high",
                                    tags="party_popper,white_check_mark,money_bag"
                                )
                                
                                print(f"💰 Total Amount Earned: ${total_amount}")
                                
                                # Small delay before cooldown notification
                                time.sleep(2)
                            
                            # Now send cooldown notification
                            self.send_notification(
                                "Cooldown Active",
                                f"⏰ {hours:.1f}h remaining\n"
                                f"Until: {self.cooldown_end.strftime('%I:%M %p IST')}\n\n"
                                f"🎯 Bot monitoring for when cooldown ends",
                                priority="default",
                                tags="hourglass"
                            )
                        
                        # Sleep until cooldown ends (with 5 second buffer)
                        sleep_time = max(60, int(remaining.total_seconds()) + 5)
                        
                        # Send notification if cooldown is ending soon (≤5 minutes)
                        if minutes <= 5 and not hasattr(self, '_cooldown_ending_notified'):
                            self._cooldown_ending_notified = True
                            self.send_notification(
                                "Cooldown Ending Soon",
                                f"⏰ {minutes:.0f} minutes remaining\nReady at: {self.cooldown_end.strftime('%I:%M %p IST')}",
                                priority="high",
                                tags="alarm_clock"
                            )
                        
                        print(f"💤 Sleeping for {sleep_time/60:.1f} minutes until cooldown ends...")
                        
                        next_check = datetime.now() + timedelta(seconds=sleep_time)
                        print(f"⏰ Next check: #{loop_count + 1} at {next_check.strftime('%I:%M %p')}")
                        
                        time.sleep(sleep_time)
                        continue
                    
                    # FLOW: 3. No task assigned and no cooldown - check for available tasks
                    print(f"   ✅ No cooldown active")
                    print(f"\n🎯 Step 3: Checking for available tasks...")
                    print(f"{'='*60}")
                    
                    # Send notification on first check only - ready to claim
                    if loop_count == 1:
                        ist = pytz.timezone('Asia/Kolkata')
                        current_ist = datetime.now(ist)
                        self.send_notification(
                            "Bot Ready",
                            f"✅ Ready to claim tasks!\n"
                            f"Time: {current_ist.strftime('%I:%M %p IST')}\n\n"
                            f"🎯 Monitoring for available tasks...",
                            priority="high",
                            tags="white_check_mark,bell"
                        )
                    
                    # Send notification that cooldown has ended (only once) - HIGH priority
                    if hasattr(self, '_cooldown_ending_notified'):
                        delattr(self, '_cooldown_ending_notified')
                        self.send_notification(
                            "Ready to Claim",
                            f"✅ Cooldown ended!\nChecking for tasks now...",
                            priority="high",
                            tags="party_popper,bell"
                        )
                    
                    # Check and claim tasks (will sync with server)
                    claimed = self.check_and_claim_tasks()
                    
                    # Use adaptive interval
                    sleep_time = self.current_check_interval
                    
                    # CRITICAL: When not in cooldown, check more frequently to catch tasks
                    # Tasks are public and disappear fast - reduce sleep time when ready to claim
                    if not self.is_in_cooldown() and self.is_within_claiming_hours():
                        # Override adaptive interval - use minimum interval when ready to claim
                        sleep_time = self.min_check_interval
                        print(f"⚡ Ready to claim - using minimum interval: {sleep_time}s")
                    
                    if claimed:
                        print(f"🎉 Task claimed! Will check again in {sleep_time}s ({sleep_time/60:.1f} minutes)")
                    else:
                        print(f"💤 Sleeping for {sleep_time}s ({sleep_time/60:.1f} minutes)...")
                    
                    # Show next check time
                    next_check = datetime.now() + timedelta(seconds=sleep_time)
                    print(f"⏰ Next check: #{loop_count + 1} at {next_check.strftime('%I:%M:%S %p')}")
                    
                    time.sleep(sleep_time)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"⚠️ Error in main loop: {e}")
                    print(f"🔄 Retrying in 60 seconds...")
                    time.sleep(60)  # Wait 1 minute on error
                    
        except KeyboardInterrupt:
            print(f"\n🛑 Bot stopped by user")
            print(f"📊 Final stats - Tasks seen today: {self.tasks_seen_today}")
            print(f"📊 Total checks performed: {loop_count}")
            
            # Get IST time
            ist = pytz.timezone('Asia/Kolkata')
            current_ist = datetime.now(ist)
            
            # Calculate cooldown status
            cooldown_status = "None"
            if self.cooldown_end:
                remaining = self.cooldown_end - datetime.now()
                if remaining.total_seconds() > 0:
                    hours = remaining.total_seconds() / 3600
                    cooldown_status = f"{hours:.1f}h remaining"
                else:
                    cooldown_status = "Expired"
            
            stop_msg = f"❎ Bot stopped By User"
            
            self.send_notification(
                "Bot Stopped",
                stop_msg,
                priority="default",
                tags="stop_sign"
            )


if __name__ == "__main__":
    bot = TaskFluxBot()
    # Fixed check interval: 3 seconds
    bot.run(check_interval=3)