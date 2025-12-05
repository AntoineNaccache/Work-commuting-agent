# Quick Start: Deploy Gmail MCP Server with ngrok

This is a streamlined guide to get your Gmail MCP server deployed with ngrok in under 5 minutes.

## Prerequisites

- Python 3.10+
- Gmail API credentials (`credentials.json`) - see main [README.md](README.md) for setup
- ngrok account (free tier works fine)

## 5-Minute Deployment

### 1. Install ngrok (2 minutes)

```bash
# Download from https://ngrok.com/download
# Or use package manager:

# macOS
brew install ngrok

# Windows (with Chocolatey)
choco install ngrok

# Linux (Snap)
snap install ngrok

# Authenticate ngrok
ngrok authtoken YOUR_AUTH_TOKEN_FROM_NGROK_DASHBOARD
```

### 2. Setup Environment (1 minute)

```bash
# Navigate to the project directory
cd mcp-gmail-main

# Install dependencies
uv sync

# Create .env file
cp .env.example .env

# Generate API key and copy it
python -c 'import secrets; print(secrets.token_urlsafe(32))'

# Edit .env and paste the API key
# Windows: notepad .env
# Mac/Linux: nano .env
```

Your `.env` should look like:
```bash
MCP_GMAIL_API_KEY=xK9mP2vL8nQ5rT7wY4zA1bC6dE3fG0hJ9iK2lM5nO8pQ  # Your generated key
MCP_GMAIL_PORT=8090
MCP_GMAIL_HOST=0.0.0.0
MCP_GMAIL_CREDENTIALS_PATH=credentials.json
MCP_GMAIL_TOKEN_PATH=token.json
```

### 3. Deploy (1 minute)

```bash
# Run the automated deployment script
python deploy_ngrok.py
```

That's it! You'll see output like:

```
============================================================
🚀 DEPLOYMENT SUCCESSFUL
============================================================

📍 Public URL: https://abc123.ngrok.io

🔑 API Key: xK9mP2vL8nQ5rT7wY4zA1bC6dE3fG0hJ9iK2lM5nO8pQ

📝 To connect to this server, use:
   URL: https://abc123.ngrok.io
   Header: X-API-Key: xK9mP2vL8nQ5rT7wY4zA1bC6dE3fG0hJ9iK2lM5nO8pQ

============================================================
```

### 4. Test Your Deployment (30 seconds)

```bash
# Test health endpoint (no auth required)
curl https://your-ngrok-url.ngrok.io/health

# Expected: {"status":"ok"}
```

## Using Your Deployed Server

### From Command Line

```bash
# Replace with your actual values
export NGROK_URL="https://your-url.ngrok.io"
export API_KEY="your-api-key"

# Test authenticated endpoint
curl -H "X-API-Key: $API_KEY" "$NGROK_URL/sse"
```

### From Python

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "https://your-ngrok-url.ngrok.io"

headers = {"X-API-Key": API_KEY}

# Test connection
response = requests.get(f"{BASE_URL}/health")
print(response.json())  # {"status": "ok"}
```

### From Your Voice Agent

Update your agent code to use the ngrok URL:

```python
import requests

class EmailAgent:
    def __init__(self, mcp_url, api_key):
        self.mcp_url = mcp_url
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

    def get_unread_emails(self):
        response = requests.post(
            f"{self.mcp_url}/sse",
            headers=self.headers,
            json={
                "method": "tools/call",
                "params": {
                    "name": "search_emails",
                    "arguments": {"is_unread": True, "max_results": 10}
                }
            }
        )
        return response.json()

# Use it
agent = EmailAgent(
    mcp_url="https://your-ngrok-url.ngrok.io",
    api_key="your-api-key"
)
emails = agent.get_unread_emails()
```

## Important Notes

### Security

- ✅ Your API key is required for all requests (except `/health`)
- ✅ Keep your `.env` file secret (already in `.gitignore`)
- ✅ Never share your API key publicly
- ✅ Regenerate API key if compromised

### ngrok URL

- Free tier ngrok URLs change each time you restart
- For a permanent URL, upgrade to ngrok paid plan ($8/month)
- Alternative: Use a cloud provider (AWS, Heroku, etc.)

### Monitoring

- ngrok dashboard: [http://127.0.0.1:4040](http://127.0.0.1:4040)
- View all requests, replay requests, inspect traffic

### Stopping the Server

Press `Ctrl+C` in the terminal running `deploy_ngrok.py`

## Troubleshooting

**"ngrok: command not found"**
- Install ngrok from [https://ngrok.com/download](https://ngrok.com/download)
- Make sure it's in your PATH

**"Missing API key" error**
- Check that you set `MCP_GMAIL_API_KEY` in `.env`
- Verify `.env` file is in the correct directory

**Can't connect to server**
- Verify server is running: `curl http://localhost:8090/health`
- Check ngrok is running: Open [http://127.0.0.1:4040](http://127.0.0.1:4040)
- Ensure `MCP_GMAIL_HOST=0.0.0.0` in `.env`

**Gmail OAuth not working**
- Make sure `credentials.json` is in the project root
- Follow the Gmail API setup in [README.md](README.md)
- Run `uv run python scripts/test_gmail_setup.py` to test

## Next Steps

Now that your server is deployed:

1. ✅ **Integrate with your voice agent** - Use the ngrok URL in your agent code
2. ✅ **Test email operations** - Try search, read, compose, send
3. ✅ **Monitor usage** - Check ngrok dashboard and Gmail API quotas
4. ✅ **Plan for production** - Consider persistent hosting (see [DEPLOYMENT.md](DEPLOYMENT.md))

## Manual Deployment (Alternative)

If the automated script doesn't work, deploy manually:

```bash
# Terminal 1: Start the server
uv run python mcp_gmail/secure_server.py

# Terminal 2: Start ngrok
ngrok http 8090
```

Copy the ngrok URL from Terminal 2 and use it with your API key.

## Full Documentation

For advanced configuration, production deployment, and troubleshooting:
- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete deployment guide
- [README.md](README.md) - Gmail API setup and usage
