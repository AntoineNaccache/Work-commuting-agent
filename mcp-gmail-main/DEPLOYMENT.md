# Deployment Guide: MCP Server with Ngrok

This guide covers both automated GitHub deployment and manual Telnyx integration for the Gmail & Calendar MCP Server.

## Table of Contents

1. [Automated GitHub Deployment](#automated-github-deployment) - Deploy on every push
2. [Manual Telnyx Deployment](#manual-telnyx-deployment) - One-time setup for Telnyx
3. [Troubleshooting](#troubleshooting)
4. [Security Best Practices](#security-best-practices)

---

# Automated GitHub Deployment

**Automatically redeploy your MCP server to ngrok whenever you push to GitHub.**

## Quick Comparison of Deployment Strategies

| Strategy | Setup Time | Cost | Best For | Auto-restart |
|----------|-----------|------|----------|--------------|
| **Self-hosted Runner** | 10 mins | Free | Development, full control | ✅ Yes |
| **Railway/Render** | 5 mins | $5-10/mo | Simple PaaS deployment | ✅ Yes |
| **VPS (DigitalOcean)** | 20 mins | $5-12/mo | Production, custom setup | ✅ Yes |

---

## Option 1: Self-Hosted GitHub Runner (Recommended for Dev)

**Pros**: Free, runs on your machine, full control, instant deployment
**Cons**: Requires your machine to be running

### Setup Steps

#### 1. Install GitHub Runner

**Windows (PowerShell as Administrator):**
```powershell
# Create runner directory
mkdir C:\actions-runner ; cd C:\actions-runner

# Download runner (check latest: https://github.com/actions/runner/releases)
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-win-x64-2.311.0.zip -OutFile actions-runner-win-x64-2.311.0.zip

# Extract
Expand-Archive -Path actions-runner-win-x64-2.311.0.zip -DestinationPath .

# Configure (get token from GitHub repo Settings → Actions → Runners)
.\config.cmd --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_REGISTRATION_TOKEN

# Install as service
.\svc.sh install
.\svc.sh start
```

**Linux/Mac:**
```bash
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz
./config.sh --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_REGISTRATION_TOKEN
sudo ./svc.sh install
sudo ./svc.sh start
```

#### 2. Configure GitHub Secrets

Go to **Settings** → **Secrets and variables** → **Actions** and add:
- `NGROK_AUTH_TOKEN`: Your ngrok auth token
- `MCP_BEARER_TOKEN`: Your MCP server bearer token

#### 3. Workflow is Already Set Up

The file [`.github/workflows/deploy-self-hosted.yml`](.github/workflows/deploy-self-hosted.yml) handles deployment automatically.

#### 4. Test It

```bash
git add .
git commit -m "Test auto-deployment"
git push origin main
```

Your server will automatically restart with the new code!

---

## Option 2: Railway Deployment

**Pros**: Managed platform, zero server maintenance
**Cons**: $5/month after free tier

### Setup Steps

#### 1. Install Railway CLI

```bash
# Linux/Mac
curl -fsSL https://railway.app/install.sh | sh

# Windows
iwr https://railway.app/install.ps1 | iex
```

#### 2. Login and Configure

```bash
railway login
railway link  # Link to your project or create new one
```

#### 3. Add Secrets to GitHub

Go to **Settings** → **Secrets and variables** → **Actions**:
- `RAILWAY_TOKEN`: Get it with `railway whoami --token`

Railway environment variables (set in Railway dashboard):
- `NGROK_AUTH_TOKEN`
- `MCP_BEARER_TOKEN`

#### 4. Deploy

Workflow [`.github/workflows/deploy-to-railway.yml`](.github/workflows/deploy-to-railway.yml) handles it.

Or deploy manually:
```bash
railway up
```

Get your URL:
```bash
railway domain
```

---

## Option 3: VPS Deployment (DigitalOcean, Linode, etc.)

**Pros**: Full control, production-ready, $5-12/month
**Cons**: Requires Linux knowledge

### Setup Steps

#### 1. Create VPS

Recommended: Ubuntu 22.04 LTS, 1GB RAM, $5-12/month

#### 2. Initial VPS Setup

```bash
# SSH into VPS
ssh root@YOUR_VPS_IP

# Update system
apt update && apt upgrade -y

# Install Python 3.10+
apt install python3.10 python3-pip -y

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Clone repository
mkdir -p ~/mcp-gmail-server
cd ~/mcp-gmail-server
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git .

# Install dependencies
uv sync

# Create log directory
sudo mkdir -p /var/log/mcp-gmail-server
sudo chown $USER:$USER /var/log/mcp-gmail-server
```

#### 3. Install Systemd Service

```bash
# Copy and configure service file
sudo cp mcp-gmail-server.service /etc/systemd/system/
sudo nano /etc/systemd/system/mcp-gmail-server.service

# Update: User=YOUR_USERNAME and WorkingDirectory=/home/YOUR_USERNAME/mcp-gmail-server

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable mcp-gmail-server
sudo systemctl start mcp-gmail-server

# Check status
sudo systemctl status mcp-gmail-server
```

#### 4. Configure GitHub Actions

Add these secrets in GitHub **Settings** → **Secrets and variables** → **Actions**:
- `VPS_HOST`: Your VPS IP
- `VPS_USERNAME`: Your SSH username
- `VPS_SSH_KEY`: Your private SSH key
- `VPS_PORT`: SSH port (usually 22)

**Generate SSH key for GitHub Actions:**
```bash
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions_key
ssh-copy-id -i ~/.ssh/github_actions_key.pub user@YOUR_VPS_IP

# Copy private key to GitHub secret
cat ~/.ssh/github_actions_key
```

#### 5. Deploy

Workflow [`.github/workflows/deploy-to-vps.yml`](.github/workflows/deploy-to-vps.yml) handles it.

Check deployment:
```bash
ssh user@YOUR_VPS_IP
sudo journalctl -u mcp-gmail-server -f
```

---

## Monitoring Your Automated Deployment

### Check Deployment Status

**GitHub Actions:**
1. Go to your GitHub repository
2. Click **Actions** tab
3. View recent workflow runs

**Self-Hosted Runner:**
```bash
# Windows
Get-Process -Name python | Where-Object {$_.CommandLine -like "*deploy_ngrok*"}

# Linux/Mac
ps aux | grep deploy_ngrok

# Get ngrok URL
curl http://localhost:4040/api/tunnels | jq '.tunnels[0].public_url'
```

**VPS:**
```bash
# Check service status
sudo systemctl status mcp-gmail-server

# View logs
sudo journalctl -u mcp-gmail-server -f

# Get ngrok URL from logs
sudo journalctl -u mcp-gmail-server | grep "ngrok URL"
```

**Railway:**
```bash
railway logs
railway status
```

### Health Checks

Test your deployment:
```bash
# Replace with your actual URL and token
curl -H "Authorization: Bearer YOUR_TOKEN" https://your-url.ngrok-free.app/sse
```

Expected response: Server-sent events connection or MCP protocol handshake.

---

## Troubleshooting Automated Deployments

### Self-Hosted Runner Issues

**Runner not appearing in GitHub:**
```bash
# Check if runner service is running
# Windows
Get-Service actions.runner.*

# Linux/Mac
sudo systemctl status actions.runner.*
```

**Port already in use:**
```bash
# Windows
netstat -ano | findstr :8090
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8090 | xargs kill -9
```

**Workflow fails with "No runner available":**
- Check if runner service is started
- Verify runner is online in GitHub repo Settings → Actions → Runners
- Check runner logs: `C:\actions-runner\_diag` or `~/actions-runner/_diag`

### Railway Issues

**Build fails:**
```bash
# Check Railway logs
railway logs

# Verify dependencies
railway run uv sync
```

**Can't access server:**
- Ensure `PORT` environment variable is set
- Verify `Procfile` uses `$PORT` variable
- Check Railway dashboard for errors

### VPS Issues

**GitHub Actions SSH fails:**
```bash
# Test SSH key locally
ssh -i ~/.ssh/github_actions_key user@YOUR_VPS_IP

# Check VPS authorized_keys
cat ~/.ssh/authorized_keys

# Verify VPS SSH service
sudo systemctl status sshd
```

**Service fails to start:**
```bash
# Check detailed error logs
sudo journalctl -u mcp-gmail-server -n 100 --no-pager

# Common fixes:
# 1. Wrong Python path
which python3

# 2. Missing dependencies
cd ~/mcp-gmail-server
uv sync

# 3. Permission issues
sudo chown -R $USER:$USER ~/mcp-gmail-server
chmod 600 ~/mcp-gmail-server/.env
```

**ngrok not connecting:**
```bash
# Verify ngrok auth token
cat ~/mcp-gmail-server/.env | grep NGROK_AUTH_TOKEN

# Test ngrok manually
ngrok http 8090
```

### Common GitHub Actions Errors

**Error: "secrets are not available"**
- Solution: Add secrets in repo Settings → Secrets and variables → Actions

**Error: "permission denied"**
- Solution: Check SSH key permissions (should be 600)
- Solution: Verify user has sudo rights (for VPS)

**Error: "workflow requires approval"**
- Solution: Go to Actions tab and approve the workflow run
- Solution: Disable approval requirement in Settings → Actions → General

---

## Rollback Procedures

### Self-Hosted Runner
```bash
# Stop current deployment
# Windows
Get-Process -Name python | Where-Object {$_.CommandLine -like "*deploy_ngrok*"} | Stop-Process

# Linux/Mac
pkill -f deploy_ngrok

# Checkout previous version
git checkout HEAD~1

# Restart
python deploy_ngrok.py --port 8090 &
```

### Railway
1. Go to Railway dashboard
2. Navigate to **Deployments**
3. Find previous successful deployment
4. Click **Redeploy**

### VPS
```bash
ssh user@YOUR_VPS_IP
cd ~/mcp-gmail-server
git log --oneline  # Find previous commit
git checkout <commit-hash>
sudo systemctl restart mcp-gmail-server
```

---

## Security for Automated Deployments

### Protect Secrets

**Update `.gitignore`:**
```gitignore
.env
.bearer_token
credentials.json
token.json
*.log
_diag/
```

**Use GitHub Secrets:**
- Never hardcode tokens in workflow files
- Use `${{ secrets.SECRET_NAME }}` syntax
- Rotate secrets periodically

### VPS Firewall

```bash
# Allow only SSH
sudo ufw allow 22/tcp
sudo ufw enable

# Check status
sudo ufw status
```

### Monitor Access

```bash
# VPS: Check SSH access logs
sudo tail -f /var/log/auth.log

# Check ngrok connections
curl http://localhost:4040/api/requests/http
```

---

# Manual Telnyx Deployment

Manual deployment guide for Telnyx AI Agent integration.

## Prerequisites

Before you begin, ensure you have:

1. ✅ **Google Cloud Project** configured with Gmail & Calendar APIs
2. ✅ **OAuth credentials** (`credentials.json`) in `mcp-gmail-main/` directory
3. ✅ **OAuth token** (`token.json`) - run the server locally first to authenticate
4. ✅ **Ngrok account** (free tier works fine)
5. ✅ **Ngrok authtoken** configured

## Step 1: Install Ngrok

### Download and Install

Visit [https://ngrok.com/download](https://ngrok.com/download) and download ngrok for your platform.

**Windows:**
```bash
# Download from website and extract to PATH
# Or use chocolatey:
choco install ngrok
```

**macOS:**
```bash
brew install ngrok
```

**Linux:**
```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

### Configure Authtoken

1. Sign up at [https://dashboard.ngrok.com/signup](https://dashboard.ngrok.com/signup)
2. Get your authtoken from [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Configure it:

```bash
ngrok config add-authtoken <your-authtoken>
```

## Step 2: Install Dependencies

```bash
cd mcp-gmail-main
uv pip install pyngrok uvicorn
```

## Step 3: Authenticate with Google (First Time Only)

Before deploying, ensure you've authenticated with Google:

```bash
uv run python -m mcp_gmail.server
```

This will:
1. Open your browser for Google OAuth
2. Ask you to grant Gmail & Calendar permissions
3. Create `token.json` file

Press Ctrl+C to stop the server once authentication is complete.

## Step 4: Deploy with Ngrok

Run the deployment script:

```bash
uv run python deploy_ngrok.py
```

### Expected Output:

```
✓ Generated new bearer token and saved to .bearer_token
✓ Creating secure MCP server wrapper...
🚀 Starting ngrok tunnel on port 8090...
✓ Ngrok tunnel established

======================================================================
🎉 MCP SERVER READY FOR TELNYX INTEGRATION
======================================================================

📡 Public URL (use this in Telnyx):
   https://abc123.ngrok-free.app

   Note: In Telnyx, use: https://abc123.ngrok-free.app/sse

🔐 Bearer Token (use this as API Key in Telnyx):
   Xy9zKj3mN8pQ2rT5vW...

📋 Telnyx Configuration:
   Name: Gmail Calendar MCP
   Type: SSE
   URL: https://abc123.ngrok-free.app/sse
   API Key: Xy9zKj3mN8pQ2rT5vW...
```

**Important:** Keep this terminal window open while you configure Telnyx!

## Step 5: Configure Telnyx AI Agent

1. **Open Telnyx Dashboard** and navigate to your AI Agent configuration

2. **Add MCP Server** - Click "Create MCP Server"

3. **Fill in the Details:**
   - **Name**: `Gmail Calendar MCP`
   - **Type**: Select `SSE` (Server-Sent Events)
   - **URL**: Paste the ngrok URL with `/sse` suffix (e.g., `https://abc123.ngrok-free.app/sse`)
   - **API Key**: Click "+ Append integration secret" and paste the bearer token

4. **Save and Test** - Telnyx will test the connection and list available MCP tools

## Deployment Options

### Local Only (No Ngrok)

Test locally without exposing publicly:

```bash
uv run python deploy_ngrok.py --no-ngrok
```

### Custom Port

```bash
uv run python deploy_ngrok.py --port 9000
```

### Regenerate Bearer Token

If token is compromised:

```bash
uv run python deploy_ngrok.py --regenerate-token
```

## Troubleshooting

### Ngrok Issues

**Error: "ngrok not found"**
- Install ngrok from https://ngrok.com/download
- Configure authtoken: `ngrok config add-authtoken <your-token>`

### Connection Issues

**Telnyx can't connect:**
1. Is the deployment script still running?
2. Did you include `/sse` at the end of the URL?
3. Did you select "SSE" type (not "HTTP")?
4. Is the bearer token copied correctly?

Test manually:
```bash
curl -H "Authorization: Bearer your-token" https://your-url.ngrok-free.app/sse
```

### OAuth Issues

**"Token has been expired or revoked":**
```bash
rm token.json
uv run python -m mcp_gmail.server  # Re-authenticate
```

## Security Best Practices

1. **Protect the Bearer Token** - Never commit `.bearer_token` file
2. **Monitor Access** - Watch server logs for unexpected requests
3. **Rotate Tokens** - Use `--regenerate-token` periodically
4. **Use HTTPS Only** - Ngrok provides this by default

## Next Steps

Test through Telnyx:
- "Check my unread emails"
- "What's on my calendar today?"
- "Find time to meet with John"

Enjoy your voice-powered assistant! 🎉
