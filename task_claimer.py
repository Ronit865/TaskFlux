import requests
import time
from datetime import datetime, timedelta
import pytz


class TaskClaimer:
    """Handles task claiming logic for TaskFlux bot"""
    
    def __init__(self, base_url, session, user_id, cooldown_file="cooldown.json"):
        self.base_url = base_url
        self.session = session
        self.user_id = user_id
        self.cooldown_file = cooldown_file
        
        # Task deadline tracking (6-hour completion limit)
        self.task_claimed_at = None
        self.task_deadline = None
        self.deadline_warning_sent = False
        self.deadline_final_warning_sent = False
        self.current_task_id = None
        self.current_task_type = None
        
    def claim_task(self, task_id, task_details=None, notification_callback=None):
        """
        Claim a specific task
        
        Args:
            task_id: The ID of the task to claim
            task_details: Optional dict with task details (type, price, subreddit, etc.)
            notification_callback: Optional function to send notifications
            
        Returns:
            bool: True if task was claimed successfully, False otherwise
        """
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
                self.current_task_id = task_id
                
                # Build detailed notification message
                task_type = task_data.get('type') or (task_details.get('type') if task_details else 'N/A')
                task_price = task_data.get('price') or (task_details.get('price') if task_details else None)
                
                # Store task type
                self.current_task_type = task_type
                
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
                
                # Print detailed task info in terminal
                self._print_task_details(
                    task_type, task_price, task_id, claim_time, 
                    deadline_time, subreddit, title, submit_url
                )
                
                # Send notification if callback provided
                if notification_callback:
                    time_left = deadline_time - datetime.now()
                    hours_left = time_left.total_seconds() / 3600
                    
                    task_info = f"🎯 Type: {task_type.upper()}\n"
                    task_info += f"💰 Price: ${task_price}\n"
                    task_info += f"⏰ Deadline: {deadline_time.strftime('%I:%M %p IST')}\n"
                    task_info += f"⏳ Time Left: {hours_left:.1f}h"
                    
                    notification_callback(
                        "Task Assigned",
                        task_info,
                        priority="urgent",
                        tags="dart"
                    )
                
                return True
                
            elif response.status_code == 400:
                # Task not available to claim
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
    
    def _print_task_details(self, task_type, task_price, task_id, claim_time, 
                           deadline_time, subreddit, title, submit_url):
        """Print detailed task information to terminal"""
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
    
    def check_task_deadline(self, notification_callback=None):
        """
        Check if task deadline is approaching and send warnings
        
        Args:
            notification_callback: Optional function to send notifications
        """
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
            
            if notification_callback:
                notification_callback(
                    "Deadline Exceeded",
                    f"⛔ {task_deadline.strftime('%I:%M %p IST')}",
                    priority="urgent",
                    tags="no_entry"
                )
            
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
            
            if notification_callback:
                notification_callback(
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
            
            if notification_callback:
                notification_callback(
                    "30 Minutes Left",
                    f"🚨 {minutes_remaining:.0f}min\n🕐 {task_deadline.strftime('%I:%M %p IST')}",
                    priority="urgent",
                    tags="fire"
                )
            
            self.deadline_final_warning_sent = True
    
    def get_task_info(self):
        """
        Get current task information
        
        Returns:
            dict: Task information or None if no active task
        """
        if not self.task_claimed_at:
            return None
        
        ist = pytz.timezone('Asia/Kolkata')
        
        if self.task_deadline:
            if self.task_deadline.tzinfo is None:
                task_deadline = ist.localize(self.task_deadline)
            else:
                task_deadline = self.task_deadline
            
            now = datetime.now(ist)
            time_remaining = task_deadline - now
            hours_remaining = time_remaining.total_seconds() / 3600
        else:
            task_deadline = None
            hours_remaining = None
        
        return {
            'task_id': self.current_task_id,
            'task_type': self.current_task_type,
            'claimed_at': self.task_claimed_at,
            'deadline': task_deadline,
            'hours_remaining': hours_remaining,
            'deadline_warning_sent': self.deadline_warning_sent,
            'deadline_final_warning_sent': self.deadline_final_warning_sent
        }
    
    def clear_task_tracking(self):
        """Clear task deadline tracking"""
        self.task_claimed_at = None
        self.task_deadline = None
        self.deadline_warning_sent = False
        self.deadline_final_warning_sent = False
        self.current_task_id = None
        self.current_task_type = None
        print(f"✅ Task tracking cleared")
    
    def has_active_task(self):
        """Check if there's an active task being tracked"""
        return self.task_claimed_at is not None or self.task_deadline is not None
