"""
Test script to verify ntfy notifications are working correctly
"""
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

def test_notification():
    """Test sending a notification via ntfy"""
    ntfy_url = os.getenv("NTFY_URL")
    
    if not ntfy_url:
        print("❌ NTFY_URL not configured in .env file")
        print("   Please add: NTFY_URL=your_ntfy_url")
        return False
    
    print(f"🔗 Testing notification to: {ntfy_url}")
    
    # Get IST time
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).strftime('%I:%M:%S %p IST')
    
    title = "Test Notification"
    message = f"✅ Notification test successful!\n⏰ Time: {current_time}"
    
    try:
        # Clean title for header
        clean_title = title.encode('latin-1', errors='ignore').decode('latin-1').strip()
        
        headers = {
            "Priority": "default",
            "Title": clean_title,
            "Content-Type": "text/plain; charset=utf-8",
            "Tags": "white_check_mark,test_tube"
        }
        
        print(f"📤 Sending test notification...")
        response = requests.post(
            ntfy_url,
            data=message.encode('utf-8'),
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Notification sent successfully!")
            print(f"   Status code: {response.status_code}")
            print(f"   Check your ntfy client/app for the notification")
            return True
        else:
            print(f"❌ Failed to send notification")
            print(f"   Status code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("📬 NTFY NOTIFICATION TEST")
    print("="*60)
    
    success = test_notification()
    
    print("="*60)
    if success:
        print("✅ Test completed successfully!")
        print("   Your notification system is working correctly.")
    else:
        print("❌ Test failed!")
        print("   Please check your NTFY_URL configuration.")
    print("="*60)
