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
        # Based on common Reddit AutoMod rules and spam patterns
        self.suspicious_patterns = [
            # Common spam/money-making schemes (high risk)
            'click here', 'free money', 'make money fast', 'get rich', 'earn money',
            'work from home', 'passive income', 'easy money', 'quick cash',
            
            # Promotional/commercial spam (high risk)
            'buy now', 'limited time', 'act now', 'don\'t miss', 'special offer',
            'discount code', 'promo code', 'coupon code', 'affiliate', 'referral link',
            
            # Link shorteners (commonly blocked by AutoMod)
            'bit.ly', 'tinyurl', 'goo.gl', 'shortened link', 't.co/',
            
            # Direct solicitation (medium-high risk)
            'dm me', 'pm me for', 'message me', 'text me', 'whatsapp', 'telegram',
            'contact me at', 'email me',
            
            # Crypto/financial spam (commonly filtered)
            'crypto', 'bitcoin', 'btc', 'ethereum', 'nft', 'forex', 
            'trading signals', 'investment opportunity', 'pump and dump',
            
            # Self-promotion (medium risk)
            'check out my', 'subscribe to my', 'follow me on', 'my channel',
            'my youtube', 'my instagram', 'my tiktok', 'my website', 'my blog',
            'visit my', 'join my',
            
            # Vote manipulation (high risk - Reddit rules violation)
            'upvote if', 'upvote this', 'give me karma', 'need karma',
            'vote manipulation', 'brigade', 'mass upvote',
            
            # Offensive/hateful content (high risk)
            'retard', 'retarded', 'faggot', 'nigger', 'kys', 'kill yourself',
            'kill urself', 'neck yourself', 'stupid ass', 'dumb fuck',
            
            # Spam indicators (medium risk)
            'check dm', 'check inbox', 'sent you a message', 'link in bio',
            'link in profile', 'click profile', 'bot account'
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
    
    def send_notification(self, title, message, priority="default", tags=None, delay_after=0.5):
        """
        Send notification via ntfy with retry logic and rate limiting
        
        Args:
            title: Notification title
            message: Notification message body
            priority: Priority level (urgent, high, default, low)
            tags: Emoji/icon tags for notification
            delay_after: Seconds to wait after successful send (prevents rate limiting)
        """
        if not self.ntfy_url:
            print(f"⚠️ No ntfy URL configured, skipping notification")
            return False
            
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
            
            # Retry logic with timeout
            max_retries = 3  # Increased from 2 to 3
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        self.ntfy_url,
                        data=full_message.encode('utf-8'),
                        headers=headers,
                        timeout=15  # Increased timeout from 10 to 15 seconds
                    )
                    
                    if response.status_code == 200:
                        print(f"✅ Notification sent: {clean_title}")
                        # Add delay after successful send to prevent rate limiting
                        if delay_after > 0:
                            time.sleep(delay_after)
                        return True  # Success
                    else:
                        print(f"⚠️ Failed to send notification: HTTP {response.status_code}")
                        if attempt < max_retries - 1:
                            print(f"   Retrying in 3 seconds...")
                            time.sleep(3)  # Increased retry delay
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        print(f"⚠️ Notification timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                        time.sleep(3)
                    else:
                        print(f"❌ Notification failed after {max_retries} timeout attempts")
                        return False
                except requests.exceptions.RequestException as req_err:
                    if attempt < max_retries - 1:
                        print(f"⚠️ Network error (attempt {attempt + 1}/{max_retries}): {req_err}")
                        print(f"   Retrying in 3 seconds...")
                        time.sleep(3)
                    else:
                        print(f"❌ Notification failed after {max_retries} attempts: {req_err}")
                        return False
            
            # If we exhausted all retries without success
            print(f"❌ Failed to send notification '{clean_title}' after {max_retries} attempts")
            return False
                        
        except Exception as e:
            print(f"❌ Error sending notification: {e}")
            return False
    
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
                
                self.send_notification(
                    "Bot Started",
                    f"🧑‍💻 {self.email}",
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
        """
        Check server for existing cooldown and sync with local state
        Returns: True if cooldown is active, False otherwise
        """
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
                        
                        # Send notification for new cooldown ONLY if not already being handled by check_task_completion
                        # We check if we have an active task - if yes, let check_task_completion handle notifications
                        if is_new_cooldown and not self.task_claimed_at:
                            self.send_notification(
                                "Cooldown Active",
                                f"⌛ {hours:.1f}h left\n⏰ {cooldown_end.strftime('%I:%M %p IST')}",
                                priority="default",
                                tags="hourglass",
                                delay_after=1.0
                            )
                            # Mark that we've sent cooldown notification on this startup
                            self._cooldown_notified_on_startup = True
                        
                        return True  # Cooldown is active
                        
                    except Exception as e:
                        print(f"⚠️ Could not parse cooldown time: {e}")
                        print(f"   allowedAfter value: {allowed_after}")
                        # Assume 24h from now if we can't parse
                        cooldown_end = datetime.now() + timedelta(hours=24)
                        self.save_cooldown(cooldown_end)
                        print(f"⏰ Server cooldown detected, estimated end: {cooldown_end.strftime('%I:%M %p IST')}")
                        return True  # Assume cooldown is active
                else:
                    # No cooldown on server
                    if self.cooldown_end:
                        if datetime.now() >= self.cooldown_end:
                            # Local cooldown expired, clear it
                            print(f"✅ Cooldown expired, ready to claim!")
                            self.cooldown_end = None
                            self.save_cooldown(None)
                            return False  # No cooldown
                        else:
                            # Server says OK but we have local cooldown that hasn't expired
                            # Trust local cooldown
                            remaining = self.cooldown_end - datetime.now()
                            hours = remaining.total_seconds() / 3600
                            print(f"⏰ Local cooldown: {hours:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
                            return True  # Cooldown still active locally
                    
                    return False  # No cooldown
            else:
                print(f"⚠️ Could not check server cooldown status (HTTP {response.status_code})")
                return False  # Assume no cooldown if can't check
                        
        except Exception as e:
            print(f"⚠️ Error syncing cooldown: {e}")
            return False  # Assume no cooldown on error
    
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
                    is_published = task.get('isPublished', False)
                    
                    # Skip tasks that are:
                    # - Already assigned to someone
                    # - Published (completed)
                    # - In invalid states
                    if assigned_to:
                        # Task is assigned to someone
                        if assigned_to == self.user_id:
                            # This is our assigned task - track it but don't add to available
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
                        # Don't add assigned tasks to available list
                        continue
                    
                    # Skip published/completed tasks
                    if is_published or status in ['published', 'completed', 'expired', 'cancelled']:
                        continue
                    
                    # Only include truly available tasks
                    if status in ['assignment-pending', 'pending', 'available', 'active']:
                        available_tasks.append(task)
                
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
                
                # Store deadline for tracking (convert to naive datetime for consistency)
                self.task_claimed_at = claim_time.replace(tzinfo=None)
                self.task_deadline = deadline_time.replace(tzinfo=None)
                self.deadline_warning_sent = False
                self.deadline_final_warning_sent = False
                
                # DON'T start cooldown yet - wait for task completion
                # Just send notification about task assignment
                
                # Build detailed notification message
                task_type = task_data.get('type') or (task_details.get('type') if task_details else 'N/A')
                task_price = task_data.get('price') or (task_details.get('price') if task_details else None)
                
                # Default to $2.00 if price is not available
                if task_price is None or task_price == 'N/A':
                    task_price = '2.00'
                
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
                print(f"💵 Price: ${task_price}")
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
                
                # Calculate time left until deadline
                time_left = deadline_time - datetime.now()
                hours_left = time_left.total_seconds() / 3600
                
                # Format notification with only necessary info
                task_info = f"🎯 Type: {task_type.upper()}\n"
                task_info += f"💵 Price: ${task_price}\n"
                task_info += f"⏰ Deadline: {deadline_time.strftime('%I:%M %p IST')}\n"
                task_info += f"⏳ Time Left: {hours_left:.1f}h"
                
                # HIGHEST PRIORITY - Task assignment is most critical
                success = self.send_notification(
                    "Task Assigned",
                    task_info,
                    priority="urgent",
                    tags="dart",
                    delay_after=1.5  # 1.5 second delay after this critical notification
                )
                
                if not success:
                    print(f"⚠️ Failed to send 'Task Assigned' notification, retrying once...")
                    time.sleep(2)
                    self.send_notification(
                        "Task Assigned",
                        task_info,
                        priority="urgent",
                        tags="dart",
                        delay_after=1.5
                    )
                
                return True
            elif response.status_code == 400:
                # Task not available to claim (already assigned, invalid status, etc.)
                print(f"⚠️ Task not available: {response.status_code}")
                try:
                    error_data = response.json()
                    error_msg = error_data.get('msg', 'Unknown error')
                    print(f"   Reason: {error_msg}")
                except:
                    print(f"   Response: {response.text}")
                return False
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
                
                # Get total amount
                task_summary = self.get_task_summary()
                total_amount = task_summary.get('totalAmount', 0) if task_summary else 0
                
                # Clear deadline tracking since task is completed
                self.task_claimed_at = None
                self.task_deadline = None
                self.deadline_warning_sent = False
                self.deadline_final_warning_sent = False
                self.current_task_id = None
                self.current_task_type = None
                
                # Reset assigned task notification flag
                if hasattr(self, '_assigned_task_notified'):
                    self._assigned_task_notified = False
                
                # Send task submitted notification first
                self.send_notification(
                    "Task Submitted",
                    f"🎯 ${total_amount}",
                    priority="high",
                    tags="dart"
                )
                
                # Wait 10 seconds before sending cooldown notification
                print(f"⏳ Waiting 10 seconds before cooldown notification...")
                time.sleep(10)
                
                # Now send cooldown notification
                self.send_notification(
                    "Cooldown Started",
                    f"⌛ 24h\n🕐 {cooldown_end_ist.strftime('%I:%M %p IST')}",
                    priority="default",
                    tags="hourglass"
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
        """
        Check if current task has been submitted by checking cooldown on server.
        Task submission is indicated by cooldown starting on the server.
        Returns True if task submitted, False otherwise.
        """
        # Only check if we have an active task
        if not self.task_claimed_at:
            return False
            
        try:
            print(f"🔍 Checking task submission status (cooldown detection)...")
            
            # Check server for cooldown WITHOUT syncing locally or sending notifications
            check_url = f"{self.base_url}/api/tasks/can-assign-task-to-self"
            response = self.session.get(check_url)
            
            if response.status_code == 200:
                data = response.json()
                default_data = data.get('default', {})
                can_claim = default_data.get('canAssign', True)
                allowed_after = default_data.get('allowedAfter')
                
                # If cooldown is detected (can't claim), task was submitted!
                if not can_claim and allowed_after:
                    print(f"✅ Cooldown detected on server - Task was submitted!")
                    print(f"🎉 Task submission confirmed!")
                    
                    # Step 1: Get task summary for total amount
                    task_summary = self.get_task_summary()
                    total_amount = task_summary.get('totalAmount', 0) if task_summary else 0
                    print(f"💰 Total Amount: ${total_amount}")
                    
                    # Step 2: Send "Task Submitted" notification
                    success = self.send_notification(
                        "Task Submitted",
                        f"🎯 ${total_amount}",
                        priority="high",
                        tags="dart",
                        delay_after=2.0  # 2 second delay after this notification
                    )
                    
                    if not success:
                        print(f"⚠️ Failed to send 'Task Submitted' notification, retrying...")
                        time.sleep(2)
                        self.send_notification(
                            "Task Submitted",
                            f"🎯 ${total_amount}",
                            priority="high",
                            tags="dart",
                            delay_after=2.0
                        )
                    
                    # Step 3: Wait before syncing cooldown
                    print(f"⏳ Waiting 10 seconds before syncing cooldown...")
                    time.sleep(10)
                    
                    # Step 4: Sync cooldown from server (this will save it locally)
                    print(f"🔄 Syncing cooldown from server...")
                    self.sync_cooldown_from_server()
                    
                    # Step 5: Send cooldown notification
                    remaining = self.get_cooldown_remaining()
                    hours = remaining.total_seconds() / 3600 if remaining else 0
                    
                    success = self.send_notification(
                        "Cooldown Started",
                        f"⌛ {hours:.1f}h\n🕐 {self.cooldown_end.strftime('%I:%M %p IST')}",
                        priority="default",
                        tags="hourglass",
                        delay_after=1.0
                    )
                    
                    if not success:
                        print(f"⚠️ Failed to send 'Cooldown Started' notification, retrying...")
                        time.sleep(2)
                        self.send_notification(
                            "Cooldown Started",
                            f"⌛ {hours:.1f}h\n🕐 {self.cooldown_end.strftime('%I:%M %p IST')}",
                            priority="default",
                            tags="hourglass",
                            delay_after=1.0
                        )
                    
                    print(f"⏰ Cooldown: {hours:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
                    
                    # Clear task tracking
                    self.task_claimed_at = None
                    self.task_deadline = None
                    self.deadline_warning_sent = False
                    self.deadline_final_warning_sent = False
                    self.current_task_id = None
                    self.current_task_type = None
                    
                    # Reset assigned task notification flag
                    if hasattr(self, '_assigned_task_notified'):
                        self._assigned_task_notified = False
                    
                    return True
            
            # No cooldown detected - task still in progress
            print(f"📋 No cooldown detected - task still in progress")
            return False
                    
        except Exception as e:
            print(f"⚠️ Error checking task completion: {e}")
            return False
    
    def check_task_deadline(self):
        """Check if task deadline is approaching and send warnings"""
        if not self.task_deadline:
            return  # No active task
        
        # Use naive datetime for consistency (all stored datetimes are naive)
        now = datetime.now()
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
                "Deadline Exceeded",
                f"⛔ {task_deadline.strftime('%I:%M %p IST')}",
                priority="urgent",
                tags="no_entry"
            )
            
            # If server didn't start cooldown, start it locally (24 hours)
            if not self.is_in_cooldown():
                print(f"⏰ Server hasn't started cooldown - starting 24h cooldown locally")
                cooldown_end = datetime.now() + timedelta(hours=24)
                self.save_cooldown(cooldown_end)
                
                # Get IST time for notification
                ist_tz = pytz.timezone('Asia/Kolkata')
                cooldown_end_ist = ist_tz.localize(cooldown_end) if cooldown_end.tzinfo is None else cooldown_end.astimezone(ist_tz)
                
                # Send cooldown notification
                self.send_notification(
                    "Cooldown Started",
                    f"⌛ 24h (Missed)\n🕐 {cooldown_end_ist.strftime('%I:%M %p IST')}",
                    priority="high",
                    tags="hourglass"
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
            
            # Reset assigned task notification flag
            if hasattr(self, '_assigned_task_notified'):
                self._assigned_task_notified = False
            
            return
        
        # Send warning at 2 hours remaining
        if hours_remaining <= 2 and not self.deadline_warning_sent:
            print(f"⚠️ Task deadline approaching: {hours_remaining:.1f}h remaining")
            self.send_notification(
                "2 Hours Left",
                f"⚠️ {hours_remaining:.1f}h\n🕐 {task_deadline.strftime('%I:%M %p IST')}",
                priority="high",
                tags="warning"
            )
            self.deadline_warning_sent = True
        
        # Send final warning at 30 minutes remaining
        elif hours_remaining <= 0.5 and not self.deadline_final_warning_sent:
            minutes_remaining = hours_remaining * 60
            print(f"🚨 URGENT: Task deadline in {minutes_remaining:.0f} minutes!")
            self.send_notification(
                "30 Minutes Left",
                f"🚨 {minutes_remaining:.0f}min\n🕐 {task_deadline.strftime('%I:%M %p IST')}",
                priority="urgent",
                tags="fire"
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
    
    def check_for_running_task(self, send_notification=True):
        """
        Check if there's a running/assigned task on the server
        send_notification: If False, skips sending notifications (for status updates only)
        """
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
            task_price = task.get('microWorkerPrice') or task.get('price', None)
            
            # Default to $2.00 if price is not available
            if task_price is None or task_price == 'N/A':
                task_price = '2.00'
            
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
                    print(f"💵 Price: ${task_price}")
                    print(f"🆔 Task ID: {task_id}")
                    print(f"⏰ Assigned at: {claimed_time.strftime('%I:%M:%S %p IST')}")
                    print(f"⏰ DEADLINE: {deadline_time.strftime('%I:%M %p IST')}")
                    print(f"⏳ Time remaining: {hours_remaining:.1f}h")
                    print(f"{'═'*60}\n")
                    
                    # Send notification only if requested (avoid duplicates)
                    if send_notification:
                        if hours_remaining > 0:
                            self.send_notification(
                                "Assigned Task Found",
                                f"📋 {task_type}\n💵 ${task_price}\n🕐 {deadline_time.strftime('%I:%M %p IST')}\n⏳ {hours_remaining:.1f}h left",
                                priority="urgent",
                                tags="pushpin"
                            )
                        else:
                            # Deadline already passed
                            self.send_notification(
                                "Task Deadline Passed",
                                f"⛔ {task_type}\n💵 ${task_price}\n🕐 {deadline_time.strftime('%I:%M %p IST')}",
                                priority="urgent",
                                tags="no_entry"
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
                
                # Send notification only if requested (avoid duplicates)
                if send_notification:
                    self.send_notification(
                        "Assigned Task Found",
                        f"🎯 {task_type}\n💵 ${task_price}\n🆔 {task_id}",
                        priority="high",
                        tags="pushpin"
                    )
            
            return True
                
        except Exception as e:
            print(f"⚠️ Error checking for assigned task: {e}")
            return False
    
    def is_within_claiming_hours(self):
        """Check if current time is within allowed claiming hours (8 AM - 11 PM IST)"""
        try:
            # Get current time in Indian timezone
            ist = pytz.timezone('Asia/Kolkata')
            now_ist = datetime.now(ist)
            current_hour = now_ist.hour
            
            # Allowed hours: 8 AM (8) to 10:59 PM (22:59)
            # Hour 23 = 11:00 PM onwards, which should be blocked
            if 8 <= current_hour < 23:
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
        Balanced checking based on actual Reddit AutoMod patterns
        Returns: (is_safe: bool, reason: str)
        """
        if not content:
            return True, "No content to check"
        
        content_lower = content.lower()
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if pattern.lower() in content_lower:
                return False, f"Contains suspicious pattern: '{pattern}'"
        
        # Check for excessive caps (>60% caps with minimum 15 letters)
        # AutoMod often flags ALL CAPS as spam
        letters = [c for c in content if c.isalpha()]
        if letters and len(letters) > 15:
            caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if caps_ratio > 0.6:
                return False, "Excessive uppercase (possible spam)"
        
        # Check for excessive punctuation/special chars (>25%)
        # Multiple exclamation marks, dollar signs often trigger filters
        special_chars = sum(1 for c in content if c in '!?$#@*')
        if len(content) > 0:
            special_ratio = special_chars / len(content)
            if special_ratio > 0.25:
                return False, "Excessive special characters"
        
        # Check for excessive emojis (>5 promotional emojis)
        emoji_count = content.count('🔥') + content.count('💰') + content.count('💵') + content.count('🚀')
        if emoji_count > 5:
            return False, "Excessive promotional emojis"
        
        # Check for very short comments (less than 5 chars)
        # Extremely short comments like "a", "ok" might be filtered
        if len(content.strip()) < 5:
            return False, "Comment too short (likely low-effort)"
        
        # Check for repetitive characters (6+ same char in a row)
        # "hahahahaha", "!!!!!!!!" commonly trigger spam filters
        for char in set(content):
            if content.count(char * 6) > 0:
                return False, f"Repetitive characters detected"
        
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
            if self.task_deadline:
                # Use naive datetime for comparison (stored deadline is naive)
                now = datetime.now()
                time_remaining = self.task_deadline - now
            else:
                time_remaining = timedelta(0)
                
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
        # FILTER AND CLAIM IMMEDIATELY - Speed is critical!
        # ═══════════════════════════════════════════════════════════
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
        
        # Quick summary
        print(f"📊 Filtering: {len(tasks)} total → {len(claimable_tasks)} claimable, {len(rejected_tasks)} rejected")
        
        # Show rejection details if any tasks were rejected
        if rejected_tasks:
            print(f"\n🚫 REJECTED TASKS DETAILS:")
            for i, rejected in enumerate(rejected_tasks[:5], 1):  # Show max 5 rejections
                task_id = rejected['task'].get('_id', 'unknown')
                print(f"   {i}. Task {task_id[:8]}...")
                print(f"      Reason: {rejected['reason']}")
                if rejected['content']:
                    # Show snippet of content
                    content_snippet = rejected['content'][:100]
                    if len(rejected['content']) > 100:
                        content_snippet += "..."
                    print(f"      Content: {content_snippet}")
            if len(rejected_tasks) > 5:
                print(f"   ... and {len(rejected_tasks) - 5} more rejected tasks")
            print()
        
        if not claimable_tasks:
            print(f"⚠️ No safe claimable tasks found!")
            
            # Build detailed rejection summary for notification
            rejection_reasons = {}
            for rejected in rejected_tasks:
                reason_key = rejected['reason'].split('-')[0].strip()  # Get main reason
                rejection_reasons[reason_key] = rejection_reasons.get(reason_key, 0) + 1
            
            rejection_summary = "\n".join([f"• {reason}: {count}" for reason, count in rejection_reasons.items()])
            
            # Send single summary notification
            self.send_notification(
                "No Claimable Tasks",
                f"🔍 {len(tasks)} found\n🚫 All rejected\n\n{rejection_summary}\n\n⏱️ Retry in 3s",
                priority="low",
                tags="mag"
            )
            return False
        
        # ═══════════════════════════════════════════════════════════
        # CLAIM THE FIRST SAFE TASK IMMEDIATELY
        # Speed is CRITICAL - claim as fast as possible!
        # ═══════════════════════════════════════════════════════════
        print(f"🎯 CLAIMING FIRST SAFE TASK IMMEDIATELY...")
        
        task = claimable_tasks[0]
        task_id = task.get('_id') or task.get('id') or task.get('taskId')
        
        if not task_id:
            print(f"❌ No task ID found!")
            return False
        
        # Claim the task (speed is critical!)
        claimed = self.claim_task(task_id, task_details=task)
        
        if not claimed:
            print(f"❌ Failed to claim task")
            return False
        
        # Task claimed successfully!
        print(f"✅ Task claimed successfully!")
        print(f"   Total tasks found: {len(tasks)}")
        print(f"   Claimable: {len(claimable_tasks)}")
        print(f"   Rejected: {len(rejected_tasks)}")
        print(f"   Claimed: ✅ 1")
        
        # Send single summary notification AFTER claiming
        summary_msg = f"📊 Task Check Summary\n\n"
        summary_msg += f"🔍 Total Found: {len(tasks)}\n"
        summary_msg += f"✅ Claimable: {len(claimable_tasks)}\n"
        summary_msg += f"🚫 Rejected: {len(rejected_tasks)}\n"
        summary_msg += f"🎯 Claimed: 1"
        summary_msg += f"\n\nTask details sent separately!"
        
        self.send_notification(
            "Task Check Summary",
            summary_msg,
            priority="default",
            tags="clipboard"
        )
        
        return True
    
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
                    
                    # FLOW: 1. Check for assigned task on server
                    has_assigned_task = self.check_for_assigned_task_on_server()
                    
                    if has_assigned_task:
                        # Task is assigned - monitor it and skip everything else
                        if self.task_deadline:
                            # Use naive datetime for comparison (stored deadline is naive)
                            now = datetime.now()
                            time_remaining = self.task_deadline - now
                            hours_remaining = time_remaining.total_seconds() / 3600
                            
                            if hours_remaining > 0:
                                print(f"\n{'='*60}")
                                print(f"⚠️  TASK MONITORING - Check #{loop_count} - {current_time}")
                                print(f"{'='*60}")
                                print(f"   Task assigned: {hours_remaining:.1f}h remaining to complete")
                                print(f"{'='*60}")
                                
                                # Send notification on first detection of assigned task
                                # Use a flag to prevent duplicate notifications
                                if not hasattr(self, '_assigned_task_notified') or not self._assigned_task_notified:
                                    self._assigned_task_notified = True
                                    self.check_for_running_task(send_notification=True)  # Get full task details and send notification
                                
                                # Check task deadline and send warnings if needed
                                self.check_task_deadline()
                                
                                # Check if task was completed (checks every 2 minutes)
                                task_completed = self.check_task_completion()
                                
                                if task_completed:
                                    # Task was completed! Exit task monitoring and check cooldown
                                    print(f"✅ Task completed! Exiting task monitoring mode.")
                                    print(f"🔄 Will check cooldown status on next iteration...")
                                    time.sleep(3)  # Short sleep before checking cooldown
                                    continue
                                
                                # Check if outside claiming hours - sleep until 8 AM
                                if not self.is_within_claiming_hours():
                                    ist = pytz.timezone('Asia/Kolkata')
                                    now_ist = datetime.now(ist)
                                    
                                    if now_ist.hour >= 23:
                                        next_8am = (now_ist + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                                    else:
                                        next_8am = now_ist.replace(hour=8, minute=0, second=0, microsecond=0)
                                    
                                    time_until_8am = next_8am - now_ist
                                    sleep_seconds = int(time_until_8am.total_seconds()) + 60
                                    hours_until = sleep_seconds / 3600
                                    
                                    print(f"😴 Task monitoring paused - Outside claiming hours")
                                    print(f"💤 Sleeping for {hours_until:.1f}h until 8 AM IST")
                                    print(f"⏰ Will resume monitoring at: {next_8am.strftime('%I:%M %p IST')}")
                                    
                                    # Send sleep notification
                                    if not hasattr(self, '_task_monitor_sleep_notified') or not self._task_monitor_sleep_notified:
                                        self._task_monitor_sleep_notified = True
                                        self.send_notification(
                                            "Task Monitor Sleeping",
                                            f"😴 {hours_until:.1f}h\n⏰ Resume: {next_8am.strftime('%I:%M %p')} IST\n📋 Task still assigned",
                                            priority="default",
                                            tags="zzz"
                                        )
                                    
                                    time.sleep(sleep_seconds)
                                    self._task_monitor_sleep_notified = False
                                    continue
                                
                                # Sleep for 2 minutes to check task submission
                                sleep_time = 120  # 2 minutes
                                print(f"💤 Sleeping for {sleep_time}s (2 minutes) to check task submission...")
                                
                                next_check = datetime.now() + timedelta(seconds=sleep_time)
                                print(f"⏰ Next check: #{loop_count + 1} at {next_check.strftime('%I:%M %p')}")
                                
                                time.sleep(sleep_time)
                                continue
                        else:
                            print(f"\n{'='*60}")
                            print(f"⚠️  TASK MONITORING - Check #{loop_count} - {current_time}")
                            print(f"{'='*60}")
                            print(f"   Task assigned on server")
                            print(f"{'='*60}")
                            
                            # Send notification on first detection of assigned task
                            # Use a flag to prevent duplicate notifications
                            if not hasattr(self, '_assigned_task_notified') or not self._assigned_task_notified:
                                self._assigned_task_notified = True
                                self.check_for_running_task(send_notification=True)
                            
                            # Check if task was submitted (cooldown detection)
                            task_completed = self.check_task_completion()
                            
                            if task_completed:
                                # Task was submitted! Exit task monitoring and check cooldown
                                print(f"✅ Task submitted! Exiting task monitoring mode.")
                                print(f"🔄 Will check cooldown status on next iteration...")
                                time.sleep(3)  # Short sleep before checking cooldown
                                continue
                            
                            # Check if outside claiming hours - sleep until 8 AM
                            if not self.is_within_claiming_hours():
                                ist = pytz.timezone('Asia/Kolkata')
                                now_ist = datetime.now(ist)
                                
                                if now_ist.hour >= 23:
                                    next_8am = (now_ist + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                                else:
                                    next_8am = now_ist.replace(hour=8, minute=0, second=0, microsecond=0)
                                
                                time_until_8am = next_8am - now_ist
                                sleep_seconds = int(time_until_8am.total_seconds()) + 60
                                hours_until = sleep_seconds / 3600
                                
                                print(f"😴 Task monitoring paused - Outside claiming hours")
                                print(f"💤 Sleeping for {hours_until:.1f}h until 8 AM IST")
                                print(f"⏰ Will resume monitoring at: {next_8am.strftime('%I:%M %p IST')}")
                                
                                # Send sleep notification
                                if not hasattr(self, '_task_monitor_sleep_notified') or not self._task_monitor_sleep_notified:
                                    self._task_monitor_sleep_notified = True
                                    self.send_notification(
                                        "Task Monitor Sleeping",
                                        f"😴 {hours_until:.1f}h\n⏰ Resume: {next_8am.strftime('%I:%M %p')} IST\n📋 Task still assigned",
                                        priority="default",
                                        tags="zzz"
                                    )
                                
                                time.sleep(sleep_seconds)
                                self._task_monitor_sleep_notified = False
                                continue
                            
                            # Task still in progress - check again in 2 minutes
                            sleep_time = 120  # 2 minutes
                            print(f"💤 Sleeping for {sleep_time}s (2 minutes) to check submission again...")
                            
                            next_check = datetime.now() + timedelta(seconds=sleep_time)
                            print(f"⏰ Next check: #{loop_count + 1} at {next_check.strftime('%I:%M %p')}")
                            
                            time.sleep(sleep_time)
                            continue
                    
                    # FLOW: 2. Check for cooldown on server
                    # Sync cooldown from server
                    server_cooldown = self.sync_cooldown_from_server()
                    
                    if server_cooldown:
                        # Server has cooldown - update local state
                        self.is_in_cooldown()  # This will update from synced cooldown_end
                    
                    # Check local cooldown (now synced with server)
                    if self.is_in_cooldown():
                        remaining = self.get_cooldown_remaining()
                        hours = remaining.total_seconds() / 3600
                        minutes = remaining.total_seconds() / 60
                        
                        print(f"\n{'='*60}")
                        print(f"⏰ COOLDOWN ACTIVE - Check #{loop_count} - {current_time}")
                        print(f"{'='*60}")
                        print(f"   {hours:.1f}h remaining until {self.cooldown_end.strftime('%I:%M %p IST')}")
                        print(f"{'='*60}")
                        
                        # Send notification on first check only (and only if not already sent during sync)
                        if loop_count == 1 and not hasattr(self, '_cooldown_notified_on_startup'):
                            # Check if cooldown just started (less than 30 minutes elapsed)
                            # This indicates a task was recently completed
                            cooldown_duration = timedelta(hours=24) - remaining
                            cooldown_elapsed_minutes = cooldown_duration.total_seconds() / 60
                            
                            if cooldown_elapsed_minutes < 30:
                                # Task was recently submitted! Send notification first
                                print(f"🎉 Recent task submission detected ({cooldown_elapsed_minutes:.1f} minutes ago)")
                                
                                # Fetch task summary to get total amount
                                task_summary = self.get_task_summary()
                                total_amount = task_summary.get('totalAmount', 0) if task_summary else 0
                                
                                # Send task submission notification
                                self.send_notification(
                                    "Task Submitted",
                                    f"💵 ${total_amount}",
                                    priority="high",
                                    tags="white_check_mark"
                                )
                                
                                print(f"💰 Total Amount Earned: ${total_amount}")
                                
                                # Small delay before cooldown notification
                                time.sleep(2)
                            
                            # Now send cooldown notification
                            self.send_notification(
                                "Cooldown Active",
                                f"⌛ {hours:.1f}h left\n🕐 {self.cooldown_end.strftime('%I:%M %p IST')}",
                                priority="default",
                                tags="hourglass"
                            )
                        
                        # Sleep until cooldown ends (with 5 second buffer)
                        sleep_time = max(60, int(remaining.total_seconds()) + 5)
                        
                        # Send notification if cooldown is ending in 10 minutes
                        if minutes <= 10 and minutes > 5 and not hasattr(self, '_cooldown_10min_notified'):
                            self._cooldown_10min_notified = True
                            self.send_notification(
                                "10 Minutes Left",
                                f"⏰ {minutes:.0f}min\n🕐 {self.cooldown_end.strftime('%I:%M %p IST')}",
                                priority="high",
                                tags="alarm_clock"
                            )
                        
                        # Send notification if cooldown is ending soon (≤5 minutes)
                        if minutes <= 5 and not hasattr(self, '_cooldown_ending_notified'):
                            self._cooldown_ending_notified = True
                            self.send_notification(
                                "Cooldown Ending",
                                f"⏰ {minutes:.0f}min\n🕐 {self.cooldown_end.strftime('%I:%M %p IST')}",
                                priority="high",
                                tags="bell"
                            )
                        
                        # Check if cooldown will end during off-hours (before 8 AM or at/after 11 PM)
                        ist = pytz.timezone('Asia/Kolkata')
                        cooldown_end_ist = self.cooldown_end
                        if cooldown_end_ist.tzinfo is None:
                            cooldown_end_ist = ist.localize(cooldown_end_ist)
                        
                        cooldown_end_hour = cooldown_end_ist.hour
                        
                        # If cooldown ends outside claiming hours (before 8 AM or at/after 11 PM)
                        if cooldown_end_hour < 8 or cooldown_end_hour >= 23:
                            # Sleep until 8 AM instead of waking up during off-hours
                            now_ist = datetime.now(ist)
                            
                            if cooldown_end_hour >= 23:
                                # Cooldown ends after 11 PM - sleep until next day 8 AM
                                next_8am = (cooldown_end_ist + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                            else:
                                # Cooldown ends before 8 AM - sleep until that day's 8 AM
                                next_8am = cooldown_end_ist.replace(hour=8, minute=0, second=0, microsecond=0)
                            
                            time_until_8am = next_8am - now_ist
                            sleep_seconds = int(time_until_8am.total_seconds()) + 60
                            hours_until = sleep_seconds / 3600
                            
                            print(f"⚠️ Cooldown ends during off-hours ({cooldown_end_ist.strftime('%I:%M %p')})")
                            print(f"😴 Will sleep until 8 AM instead")
                            print(f"💤 Sleeping for {hours_until:.1f}h until 8 AM IST")
                            print(f"⏰ Will resume at: {next_8am.strftime('%I:%M %p IST')}")
                            
                            # Send adjusted sleep notification
                            if not hasattr(self, '_cooldown_offhours_notified') or not self._cooldown_offhours_notified:
                                self._cooldown_offhours_notified = True
                                self.send_notification(
                                    "Sleeping Until 8 AM",
                                    f"⏰ Cooldown ends at {cooldown_end_ist.strftime('%I:%M %p')} (off-hours)\n😴 {hours_until:.1f}h\n☀️ Resume: {next_8am.strftime('%I:%M %p')} IST",
                                    priority="default",
                                    tags="zzz"
                                )
                            
                            time.sleep(sleep_seconds)
                            self._cooldown_offhours_notified = False
                            continue
                        
                        # Cooldown ends during claiming hours - sleep until cooldown ends
                        print(f"💤 Sleeping for {sleep_time/60:.1f} minutes until cooldown ends...")
                        
                        next_check = datetime.now() + timedelta(seconds=sleep_time)
                        print(f"⏰ Next check: #{loop_count + 1} at {next_check.strftime('%I:%M %p')}")
                        
                        time.sleep(sleep_time)
                        continue
                    
                    # FLOW: 3. No task assigned and no cooldown - check for available tasks
                    print(f"\n{'='*60}")
                    print(f"🔍 CHECKING TASKS - Check #{loop_count} - {current_time}")
                    print(f"{'='*60}")
                    
                    # Send notification on first check only - ready to claim
                    if loop_count == 1:
                        ist = pytz.timezone('Asia/Kolkata')
                        current_ist = datetime.now(ist)
                        self.send_notification(
                            "Bot Ready",
                            f"🟢 Ready\n🕐 {current_ist.strftime('%I:%M %p IST')}",
                            priority="high",
                            tags="green_circle"
                        )
                    
                    # Send notification that cooldown has ended (only once) - HIGH priority
                    if hasattr(self, '_cooldown_ending_notified'):
                        delattr(self, '_cooldown_ending_notified')
                        self.send_notification(
                            "Ready",
                            f"🔥 Cooldown ended",
                            priority="high",
                            tags="robot"
                        )
                    
                    # Clear 10-minute notification flag if it exists
                    if hasattr(self, '_cooldown_10min_notified'):
                        delattr(self, '_cooldown_10min_notified')
                    
                    # Check and claim tasks (will sync with server)
                    claimed = self.check_and_claim_tasks()
                    
                    if claimed:
                        # Task claimed! Start monitoring immediately
                        print(f"\n✅ Task claimed successfully!")
                        print(f"⏰ Switching to task monitoring mode (will check status immediately)")
                        print(f"{'='*60}")
                        time.sleep(3)  # Short 3-second delay before first check
                        continue
                    
                    # No task claimed - it could be:
                    # 1. Outside claiming hours (8 AM - 11 PM IST)
                    # 2. No tasks available
                    # 3. All tasks rejected (unsafe content)
                    
                    # Check if currently outside claiming hours and sleep until 8 AM
                    ist = pytz.timezone('Asia/Kolkata')
                    now_ist = datetime.now(ist)
                    current_hour = now_ist.hour
                    
                    if current_hour < 8 or current_hour >= 23:
                        # Outside claiming hours - sleep until 8 AM IST
                        if now_ist.hour >= 23:
                            # After 11 PM - wait until 8 AM tomorrow
                            next_8am = (now_ist + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                        else:
                            # Before 8 AM - wait until 8 AM today
                            next_8am = now_ist.replace(hour=8, minute=0, second=0, microsecond=0)
                        
                        time_until_8am = next_8am - now_ist
                        sleep_seconds = int(time_until_8am.total_seconds()) + 60  # Add 1 minute buffer
                        hours_until = sleep_seconds / 3600
                        
                        print(f"{'='*60}")
                        print(f"😴 Sleeping for {hours_until:.1f}h until 8 AM IST")
                        print(f"⏰ Next check: #{loop_count + 1} at {next_8am.strftime('%I:%M %p IST on %B %d')}")
                        print(f"{'='*60}")
                        
                        # Send sleep notification (only once per sleep session)
                        if not hasattr(self, '_sleep_notified') or not self._sleep_notified:
                            self._sleep_notified = True
                            self.send_notification(
                                "Bot Sleeping",
                                f"😴 {hours_until:.1f}h\n⏰ Resume: {next_8am.strftime('%I:%M %p')} IST",
                                priority="default",
                                tags="zzz"
                            )
                        
                        time.sleep(sleep_seconds)
                        
                        # Reset sleep notification flag when waking up
                        self._sleep_notified = False
                        
                        # Send wake-up notification
                        self.send_notification(
                            "Bot Awake",
                            f"☀️ Ready to claim!\n🕐 {next_8am.strftime('%I:%M %p')} IST",
                            priority="high",
                            tags="sunny"
                        )
                        
                        continue
                    
                    # No task claimed - check again in 3 seconds
                    print(f"{'='*60}")
                    sleep_time = 3
                    
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
            
            self.send_notification(
                "Bot Stopped",
                f"💀 Stopped",
                priority="default",
                tags="robot"
            )


if __name__ == "__main__":
    bot = TaskFluxBot()
    # Fixed check interval: 3 seconds
    bot.run(check_interval=3)