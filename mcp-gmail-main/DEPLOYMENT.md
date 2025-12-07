# Deployment Guide: MCP Server with Ngrok for Telnyx

This guide walks you through deploying the Gmail & Calendar MCP Server via ngrok for Telnyx AI Agent integration.

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
