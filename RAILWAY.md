# TaskFlux Bot - Railway Deployment Guide

## Quick Deploy to Railway

### 1. Prerequisites
- Railway account ([railway.app](https://railway.app))
- GitHub repository with this code

### 2. Deploy Steps

1. **Push to GitHub** (if not already)
   ```bash
   git add .
   git commit -m "Add Railway deployment files"
   git push
   ```

2. **Create New Project on Railway**
   - Go to [railway.app](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your TaskFlux repository

3. **Configure Environment Variables**
   In Railway dashboard, add these variables:
   ```
   EMAIL=your_taskflux_email@gmail.com
   PASSWORD=your_taskflux_password
   NTFY_URL=https://ntfy.sh/your_topic_name
   ```

4. **Deploy**
   - Railway will automatically detect `Procfile` and `requirements.txt`
   - Deployment starts automatically
   - Check logs to verify bot is running

### 3. Files Created

- **Procfile** - Tells Railway how to run the bot
- **requirements.txt** - Lists Python dependencies
- **RAILWAY.md** - This deployment guide

### 4. Verify Deployment

**Check Logs:**
- Go to Railway dashboard → Your project → Deployments
- Click on latest deployment to see logs
- Look for: `✅ Login successful!`
- Look for: `✅ Command listener thread started`

**Test Commands:**
1. Send `status` from ntfy app
2. Should respond within 10 seconds
3. Try `help` to see all commands

### 5. Monitoring

**Railway Dashboard:**
- View real-time logs
- Monitor resource usage
- Restart service if needed

**Via ntfy:**
- Send `status` anytime to check bot health
- Bot sends notifications for important events

### 6. Troubleshooting

**Bot not starting:**
- Check environment variables are set correctly
- Verify `EMAIL`, `PASSWORD`, `NTFY_URL` are correct
- Check Railway logs for error messages

**Commands not responding:**
- Verify `NTFY_URL` is correct
- Check bot logs for connection errors
- Send `status` and wait up to 10 seconds

**Login failures:**
- Verify TaskFlux credentials are correct
- Check if TaskFlux website is accessible
- Review Railway logs for specific errors

### 7. Updating the Bot

**Push changes to GitHub:**
```bash
git add .
git commit -m "Update bot"
git push
```

Railway will automatically redeploy on push!

### 8. Cost

- Railway free tier: 500 hours/month ($5 credit)
- This bot uses minimal resources
- Should run free for most users

### 9. Alternative: Manual Deployment

If you prefer not to use GitHub:

1. Install Railway CLI
   ```bash
   npm install -g railway
   ```

2. Login and deploy
   ```bash
   railway login
   railway init
   railway up
   ```

3. Set environment variables
   ```bash
   railway variables set EMAIL=your_email
   railway variables set PASSWORD=your_password
   railway variables set NTFY_URL=your_ntfy_url
   ```

---

## Bot Commands Reference

Send these from your ntfy mobile app:

- `pause` - Pause task claiming
- `unpause` - Resume task claiming
- `status` - Get bot status
- `time 8-23` - Set active hours (8 AM - 11 PM)
- `help` - Show all commands

**Response time:** Commands respond within 10 seconds, even during long cooldowns!

---

## Need Help?

- Check Railway logs for errors
- Verify all environment variables
- Test ntfy connection with `status` command
- Review `deployment_verification.md` for detailed checks
