# 🤖 TaskFlux Bot - Automated Task Claimer

> **Intelligent bot for TaskFlux that automatically claims Reddit tasks, tracks deadlines, manages cooldowns, and sends real-time notifications**

---

## ⚙️ Environment Configuration (.env)

**🔴 REQUIRED: Create a `.env` file first!**

```env
# TaskFlux Account Credentials
EMAIL=your_email@gmail.com
PASSWORD=your_taskflux_password

# Notification Service (ntfy.sh)
NTFY_URL=https://ntfy.sh/your_topic_name

# Bot Performance Mode (RECOMMENDED: true)
CONTINUOUS_MODE=true
```

### 📋 Configuration Details:

| Variable | Description | Example |
|----------|-------------|---------|
| `EMAIL` | Your TaskFlux account email | `rajdhimmar4@gmail.com` |
| `PASSWORD` | Your TaskFlux account password | `mySecurePassword123` |
| `NTFY_URL` | ntfy.sh notification URL | `https://ntfy.sh/taskflux_bot` |
| `CONTINUOUS_MODE` | Enable rapid checking (30-60s intervals) | `true` ⭐ RECOMMENDED |

### 🔔 Setting up ntfy Notifications:

1. **Install ntfy app** on your phone ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS](https://apps.apple.com/us/app/ntfy/id1625396347))
2. **Choose a unique topic name** (e.g., `taskflux_raj_2025`)
3. **Subscribe to your topic** in the ntfy app
4. **Add to `.env`**: `NTFY_URL=https://ntfy.sh/taskflux_raj_2025`

---

## 🚀 Quick Start

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` file with your credentials (see above)

### 3. Run the Bot
```powershell
python taskflux_bot.py
```
Or double-click `run_bot.bat`

---

## ✨ Features

### 🎯 Core Automation
- ✅ **Auto-login** to TaskFlux
- ✅ **Auto-claim tasks** (RedditCommentTask & RedditReplyTask only)
- ✅ **1-minute task completion checks** (when task is assigned)
- ✅ **Smart cooldown handling** (sleeps entire 24h duration)
- ✅ **Server sync** (accurate cooldown tracking from TaskFlux API)
- ✅ **Persistent state** (survives bot restarts via `cooldown.json`)

### ⏰ Advanced Tracking
- ✅ **6-hour deadline monitoring** (automatic warnings at 2h and 30min)
- ✅ **Task completion detection** (checks every 1 minute after assignment)
- ✅ **Total earnings display** (shows amount from task-summary API)
- ✅ **Time-based claiming** (8 AM - 11 PM IST only)
- ✅ **IST timezone** (all times in Indian Standard Time)

### 🛡️ Safety & Intelligence
- ✅ **Content safety filtering** (rejects AutoMod triggers)
- ✅ **Spam pattern detection** (avoids risky content)
- ✅ **Task type filtering** (only safe Reddit tasks)
- ✅ **Detailed task preview** (type, price, subreddit, content)

### 📱 Real-time Notifications
- ✅ **Bot status** (started, stopped, ready)
- ✅ **Task alerts** (available, claimed, completed)
- ✅ **Deadline warnings** (2h, 30min, exceeded)
- ✅ **Cooldown updates** (active, ending soon, ended)
- ✅ **Earnings summary** (total amount earned)

### ⚡ Performance Modes

#### Continuous Mode (RECOMMENDED ⭐)
**Set `CONTINUOUS_MODE=true` for best results!**

- ✅ Checks every **30-60 seconds** for tasks
- ✅ **1-minute checks** during assigned tasks
- ✅ **Instant claiming** (beats competitors)
- ✅ **Smart sleep** (skips checks during cooldown)
- ✅ **Resource efficient** (only checks when needed)

#### Adaptive Mode (Legacy)
**Set `CONTINUOUS_MODE=false`** (not recommended)

- Checks every 3-10 minutes
- Slower task claiming
- May miss fast-disappearing tasks

---

## 🔄 How It Works

### Bot Workflow:

1. **Login** → Authenticate with TaskFlux
2. **Check Assigned Task** → Monitor if task is already assigned
   - If yes → Check every **1 minute** for completion
3. **Check Cooldown** → Sync with server
   - If active → Sleep entire 24h duration
4. **Check Time** → 8 AM - 11 PM IST only
5. **Check Tasks** → Fetch available tasks
6. **Filter & Claim** → Safe tasks only
7. **Monitor Completion** → 1-minute checks
8. **Task Completed** → Get total amount + send notifications
9. **Cooldown Started** → Sleep 24 hours
10. **Repeat** → Wake up and start again

### Completion Detection:
- Checks every **60 seconds** when task is assigned
- Monitors `/api/tasks/can-assign-task-to-self` endpoint
- Detects cooldown = task completed
- Fetches earnings from `/api/tasks/task-summary`

### Notification Sequence:
1. 🎉 **Task Completed** (with total amount earned)
2. ⏰ **Cooldown Started** (24h countdown)

---

## 📱 Notification Guide

### All Notifications:

| Notification | When | Priority |
|--------------|------|----------|
| 🤖 Bot Started | Bot launches | Default |
| ✅ Ready to Claim | Cooldown ended | High |
| 📋 Tasks Available | Tasks detected | High |
| 🎯 TASK ASSIGNED | Task claimed | 🔴 Urgent |
| ⚠️ 2 Hours Left | Deadline warning | High |
| 🚨 30 Minutes Left | Final warning | 🔴 Urgent |
| ❌ Deadline Exceeded | Missed deadline | 🔴 Urgent |
| 🎉 Task Completed | Task done + earnings | High |
| ⏰ Cooldown Started | 24h sleep begins | Default |
| 🔔 Cooldown Ending | 5min warning | High |
| ❎ Bot Stopped | Manual shutdown | Default |

---

## ⏰ Deadline System

Tasks **MUST** be completed within **6 hours**!

### Timeline:

| Time | Alert | Action |
|------|-------|--------|
| 6h 00m | 🎯 Assigned | Start working |
| 2h 00m | ⚠️ Warning | Speed up |
| 0h 30m | 🚨 Urgent | Complete now! |
| 0h 00m | ❌ Failed | Cooldown starts |

---

## 🛡️ Safety Filtering

Bot **rejects** tasks with:

- ❌ Spam patterns ("free money", "click here")
- ❌ Promotional content ("buy now", "discount code")
- ❌ Self-promotion ("subscribe to my")
- ❌ Shortened URLs (bit.ly, tinyurl)
- ❌ Low-effort content (too short, repetitive)
- ❌ Excessive caps/emojis/special chars

**✅ Only claims:** Safe, natural Reddit comments/replies

---

## 🔧 Advanced Options

### View Cooldown Status
```powershell
cat cooldown.json
```

### Force Reset (Use Carefully!)
```powershell
Remove-Item cooldown.json
python taskflux_bot.py
```

### Change ntfy Topic
Edit `.env`:
```env
NTFY_URL=https://ntfy.sh/new_topic_name
```

---

## 📂 Project Structure

```
TaskFlux/
├── .env                    # 🔒 Credentials (DO NOT COMMIT!)
├── .gitignore             # Git exclusions
├── taskflux_bot.py        # 🤖 Main bot
├── cooldown.json          # 💾 State (auto-generated)
├── login_response.json    # 📝 Login cache
├── requirements.txt       # 📦 Dependencies
├── run_bot.bat           # 🚀 Windows launcher
└── README.md             # 📖 This file
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| ❌ Login fails | Update `EMAIL`/`PASSWORD` in `.env` |
| 📱 No notifications | Subscribe to ntfy topic in app |
| ⏰ Wrong cooldown | Bot auto-syncs on startup |
| 🕐 Not claiming | Check if 8 AM - 11 PM IST |
| 🚫 All tasks rejected | Bot filtering works - wait for safe tasks |

---

## 💡 Pro Tips

✅ **Enable** `CONTINUOUS_MODE=true`  
✅ **Run** bot 24/7  
✅ **Complete** tasks immediately  
✅ **Monitor** notifications  
✅ **Set** phone alarms for deadlines

---

## 🔒 Security

- 🔐 Use strong, unique password
- 🚫 Never commit `.env` to GitHub
- 🔒 Keep ntfy topic private
- ✅ `.gitignore` already configured

---

## 📦 Requirements

```txt
requests==2.31.0
python-dotenv==1.0.0
pytz==2023.3
```

**Python:** 3.8+  
**OS:** Windows 10/11 (or Linux/Mac with modifications)

---

## 📊 Sample Output

```
🔐 Logging in as rajdhimmar4@gmail.com...
✅ Login successful!

=========================================
🔍 CHECKING SERVER STATUS
=========================================
✅ No active cooldown - ready to claim!
=========================================

==================================================
🔄 Check #1 at 05:54 PM
✅ No cooldown
🔍 Checking for available tasks...

📋 Found 2 task(s) available
✅ Found 1 safe claimable task(s)
🎯 Claiming the first safe task...

════════════════════════════════════════════════
🎯 TASK DETAILS
════════════════════════════════════════════════
📋 Type: REDDITCOMMENTTASK
💰 Price: $2.00
⏰ DEADLINE: 11:54 PM IST (6 hours)
📍 Subreddit: r/AskReddit
🔗 Submit: https://taskflux.net/tasks/.../submission
════════════════════════════════════════════════

(1 minute monitoring...)

🔍 Checking task completion status...
✅ Task completed! Cooldown detected from server.
🎉 Task completion confirmed!
💰 Total Amount: $23.00
⏰ Cooldown: 24.0h remaining until 05:54 PM IST
```

---

## ❓ FAQ

**Q: Why 1-minute checks?**  
A: Detects task completion quickly for instant notifications.

**Q: Can I run multiple bots?**  
A: No - one bot per account to avoid conflicts.

**Q: What if I miss the deadline?**  
A: Task fails, cooldown starts automatically.

**Q: Why are tasks rejected?**  
A: Safety filtering prevents AutoMod removals.

---

## 🆕 Changelog

### v2.1 - November 2025
- ✅ 1-minute task completion checks
- ✅ Total earnings from task-summary API
- ✅ Separate completion + cooldown notifications

### v2.0 - October 2025
- ✅ Priority-based notifications
- ✅ Enhanced deadline tracking
- ✅ Improved safety filtering

---

## ⚠️ Disclaimer

For **personal educational use only**.  
Follow TaskFlux Terms of Service.  
Author not responsible for account issues.

---

## 📄 License

MIT License - Free to use and modify

---

**Status**: ✅ Ready to run!  
**Updated**: November 6, 2025  
**Version**: 2.1.0

Made with ❤️ for TaskFlux automation
