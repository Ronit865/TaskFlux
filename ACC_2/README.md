# 🤖 TaskFlux Bot

**Automated TaskFlux bot with smart cooldown monitoring, time-based claiming (8 AM - 11 PM IST), auto-retry login, and comprehensive mobile notifications via ntfy.sh.**

---

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create `.env` File
```env
EMAIL=your_email@gmail.com
PASSWORD=your_taskflux_password
NTFY_URL=https://ntfy.sh/your_unique_topic
```

**Environment Variables:**
- `EMAIL`: Your TaskFlux account email
- `PASSWORD`: Your TaskFlux password
- `NTFY_URL`: Your ntfy notification URL (for mobile alerts)

### 3. Setup Mobile Notifications
- Install [ntfy app](https://ntfy.sh) (Android/iOS)
- Subscribe to your topic name
- Test: `curl -d "Test" ntfy.sh/your_unique_topic`

### 4. Run Bot
```bash
python taskflux_bot.py
```

---

## ⚡ Key Features

**Speed & Reliability**
- 🔥 3-second task checking (claims before others)
- 🔄 Auto-retry with 3 attempts on failures
- 🌐 30-second timeouts for stability
- 💾 Persistent state (`cooldown.json`)

**Intelligence**
- 🛡️ Content safety filtering (80+ patterns)
- 🎯 Reddit tasks only (Comment/Reply)
- 🔄 Server-synced cooldown (24h)
- 🕐 Active hours: 8 AM - 11 PM IST only

**Tracking & Alerts**
- ⏰ 6-hour deadline monitoring
- 🚨 Deadline warnings: 2h & 30min
- 💰 Total earnings display
- 📱 Mobile push notifications
- ⏱️ Smart cooldown alerts: 1h, 10min, 5min, 2min

---

## 📱 Notifications

| Emoji | Event | Priority | When |
|-------|-------|----------|------|
| 🤖 | Bot Started | Default | On login |
| ❌ | Login Failed | 🔴 URGENT | After 3 failed attempts |
| 🟢 | Bot Ready | ⚠️ HIGH | Ready to claim |
| 🎯 | Task Assigned | 🔴 URGENT | Task claimed |
| ⏰ | 2 Hours Left | ⚠️ HIGH | 2h before deadline |
| 🔥 | 30 Minutes Left | 🔴 URGENT | 30min before deadline |
| ✅ | Task Submitted | ⚠️ HIGH | Task completed |
| ⏱️ | Cooldown Started | Default | After submission |
| ⏰ | 1 Hour Left | ⚠️ HIGH | 1h before cooldown ends |
| ⏰ | 10 Minutes Left | ⚠️ HIGH | 10min before cooldown ends |
| 🔔 | 5 Minutes Left | ⚠️ HIGH | 5min before cooldown ends |
| 🔥 | Cooldown Ending | 🔴 URGENT | 2min before cooldown ends |
| 😴 | Off-Hours Sleep | Default | Outside 8 AM-11 PM |
| ☀️ | Bot Awake | ⚠️ HIGH | At 8 AM IST |
| ⚠️ | Bot Error | ⚠️ HIGH | Error occurred |
| 💥 | Bot Crashed | 🔴 URGENT | Critical failure |
| 🛑 | Bot Stopped | Default | Manual stop |

**Total: 17+ notification types for complete monitoring!**

---

## 🔄 How It Works

```
Login → Check Current State (assigned task or cooldown)
   ↓
   ├─ Has assigned task? → Monitor every 2 minutes → Task submitted → Cooldown starts
   ├─ In cooldown? → Smart sleep with alerts (1h, 10min, 5min, 2min)
   └─ Ready to claim? → Check if 8 AM - 11 PM → Search and claim task
                              ↓
                        Outside hours? Sleep until 8 AM
```

**Time-Based Claiming:** Only searches for tasks between 8 AM - 11 PM IST  
**Smart Wake-Up:** Calculates sleep to wake before each alert threshold  
**Completion Detection:** Monitors cooldown endpoint = task submitted  
**Auto-Retry:** 3 login attempts with 30-second timeout

---

## 🛡️ Safety Filters

**Rejects tasks with:**
- Spam patterns (click here, free money)
- Promotional content (buy now, discount)
- Self-promotion (subscribe, follow me)
- Shortened URLs (bit.ly, tinyurl)
- Low-effort content
- Excessive caps/emojis

---

## 📂 Files

```
.env                  # Credentials (create this)
taskflux_bot.py       # Main bot
cooldown.json         # State (auto-generated)
requirements.txt      # Dependencies
run_bot.bat          # Windows launcher
```

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| Login fails | Check `.env` credentials |
| No notifications | Subscribe to ntfy topic |
| Wrong cooldown | Bot auto-syncs on start |
| All tasks rejected | Safety filter working |

---

## ⚙️ Technical Details

**Check Intervals:**
- Task searching: Every cooldown cycle (24 hours)
- Task monitoring: 2 minutes (when assigned)
- Cooldown sync: 3 seconds (verifying status)

**Smart Wake-Up System:**
- Calculates next alert time (1h, 10min, 5min, 2min before cooldown ends)
- Sleeps until alert time instead of full duration
- Ensures timely notifications without constant checking

**Active Hours:**
- Claims tasks only between 8 AM - 11 PM IST
- Sleeps during off-hours, wakes at 8 AM

**Timezone:** All times in IST (Asia/Kolkata)

**Requirements:**
- Python 3.8+
- requests, python-dotenv, pytz

---

## 💡 Tips

✅ Run 24/7 for best results  
✅ Complete tasks immediately  
✅ Enable phone notifications  
✅ Never share `.env` file

---

## 📊 Sample Output

```
🔐 Logging in...
✅ Login successful!
🤖 Bot started successfully!

🔄 Checking current state...
✅ No assigned task, no active cooldown

🔍 Checking for tasks...
📋 Found 3 tasks
🎯 Claiming task: RedditCommentTask ($2.00)

════════════════════════════════════
🎯 TASK ASSIGNED
════════════════════════════════════
📋 RedditCommentTask
💰 $2.00
⏰ Deadline: 11:54 PM IST (6h)
📍 r/AskReddit
════════════════════════════════════

(Monitoring every 2 minutes...)

⏰ 2 hours left until deadline!

✅ Task submitted detected!
💰 Earned: $2.00
⏱️ Cooldown started: 24 hours

⏰ 1 hour left in cooldown
⏰ 10 minutes left in cooldown
🔔 5 minutes left in cooldown
🔥 Cooldown ending in 2 minutes!

🟢 Cooldown ended! Ready to claim next task.
```
```

---

## 🔒 Security

- Never commit `.env`
- Keep ntfy topic private
- Use strong password
- `.gitignore` configured

---

**Version:** 3.0  
**Updated:** January 2025  
**Status:** ✅ Production Ready (with hosting-grade error notifications)

---

*For educational use. Follow TaskFlux TOS.*
