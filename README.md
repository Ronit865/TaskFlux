# 🤖 TaskFlux Bot

**Automated TaskFlux bot with 3-second task detection, deadline tracking, and mobile notifications.**

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
MAX_TASKS=5
```

**Environment Variables:**
- `EMAIL`: Your TaskFlux account email
- `PASSWORD`: Your TaskFlux password
- `NTFY_URL`: Your ntfy notification URL
- `MAX_TASKS`: Max tasks to claim when >2 available (default: 1, range: 1-10)
  - Not set or `MAX_TASKS=1` → Conservative (1 task when >2 available)
  - `MAX_TASKS=5` → Aggressive (5 tasks concurrently for speed)
  - `MAX_TASKS=10` → Maximum (10 tasks, may hit rate limits)

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

**Speed**
- 🔥 3-second task checking (claims before others)
- ⚡ Concurrent claiming (up to MAX_TASKS at once)
- 💨 Sub-second multi-task claiming
- 🚀 Thread-based parallel requests

**Intelligence**
- 🛡️ Content safety filtering (80+ patterns)
- 🎯 Reddit tasks only (Comment/Reply)
- 🔄 Server-synced cooldown (24h)
- 💾 Persistent state (`cooldown.json`)

**Tracking**
- ⏰ 6-hour deadline monitoring
- 🚨 Warnings at 2h & 30min
- 💰 Total earnings display
- 📱 Mobile push notifications

---

## 📱 Notifications

| Emoji | Event | Priority |
|-------|-------|----------|
| 🟢 | Bot online | - |
| 📋 | Task assigned | 🔴 |
| ✅ | Task submitted | ⚠️ |
| ⏱️ | Cooldown active | - |
| ⏰ | Deadline warning | ⚠️ |
| 🚨 | 30min left | 🔴 |
| ❌ | Deadline missed | 🔴 |
| 🟢 | Ready to claim | ⚠️ |
| 🔴 | Bot stopped | - |

---

## 🔄 How It Works

```
Login → Check Assigned Task → Monitor (60s checks)
   ↓                              ↓
Sync Cooldown → Sleep 24h    Task Done
   ↓                              ↓
Check Tasks (3s) → Filter → Claim (1-5 tasks) → Monitor → Loop
                              ↓
                    >2 tasks? Claim MAX_TASKS concurrently
                    ≤2 tasks? Claim 1 task
```

**Multi-Task Claiming:** When >2 tasks available, claims up to MAX_TASKS simultaneously  
**Completion Detection:** Monitors cooldown endpoint = task submitted  
**Earnings Tracking:** Fetches from `/api/tasks/task-summary`

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
- Task checking: 3 seconds (fixed)
- Task monitoring: 60 seconds (when assigned)
- Cooldown sleep: 24 hours (full duration)

**Multi-Task Claiming:**
- Threshold: >2 available tasks triggers multi-claim
- Max concurrent: Configurable via MAX_TASKS (default: 1)
- Speed: All claims sent simultaneously via ThreadPoolExecutor
- Safety limit: 1-10 tasks maximum

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

🔄 Check #1 at 05:54 PM
🔍 Checking for tasks...
📋 Found 6 tasks
🎯 CLAIMING 5 TASKS CONCURRENTLY (more than 3 available, MAX_TASKS=5)...

✅ Task 1/5 claimed successfully!
✅ Task 2/5 claimed successfully!
✅ Task 3/5 claimed successfully!
✅ Task 4/5 claimed successfully!
✅ Task 5/5 claimed successfully!

════════════════════════════════════
🎯 TASK DETAILS (Task 1)
════════════════════════════════════
📋 RedditCommentTask
💰 $2.00
⏰ Deadline: 11:54 PM IST (6h)
📍 r/AskReddit
════════════════════════════════════

(5 tasks claimed in ~1 second!)
(Monitoring every 60s...)

✅ Tasks submitted!
💰 Total: $33.00
⏱️ Cooldown: 24h
```

---

## 🔒 Security

- Never commit `.env`
- Keep ntfy topic private
- Use strong password
- `.gitignore` configured

---

**Version:** 2.3  
**Updated:** Nov 8, 2025  
**Status:** ✅ Production Ready

---

*For educational use. Follow TaskFlux TOS.*
