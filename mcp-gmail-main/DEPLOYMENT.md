# Deploying Gmail MCP Server with ngrok

This guide explains how to deploy your Gmail MCP server securely using ngrok with API key authentication.

## Quick Start

### 1. Install ngrok

Download and install ngrok from [https://ngrok.com/download](https://ngrok.com/download)

```bash
# After downloading, authenticate ngrok with your account
ngrok authtoken YOUR_AUTH_TOKEN
```

### 2. Set up environment

```bash
# Copy the example environment file
cp .env.example .env

# Generate a secure API key
python -c 'import secrets; print(secrets.token_urlsafe(32))'

# Edit .env and add your API key
# On Windows: notepad .env
# On Linux/Mac: nano .env
```

### 3. Deploy

```bash
# Install dependencies
uv sync

# Run the deployment script
python deploy_ngrok.py
```

The script will:
- ✅ Check for ngrok installation
- ✅ Verify/create .env configuration
- ✅ Start the secure MCP server
- ✅ Create an ngrok tunnel
- ✅ Display connection information

## Architecture

### Security Layers

1. **API Key Authentication**: All requests (except `/health`) require an `X-API-Key` header
2. **ngrok Tunnel**: Secure HTTPS tunnel to your local server
3. **Gmail OAuth**: Standard OAuth 2.0 authentication with Google

### Components

```
Client → ngrok (HTTPS) → API Key Middleware → MCP Server → Gmail API
```

## Configuration

### Environment Variables

Edit your `.env` file:

```bash
# Required: Your API key (keep this secret!)
MCP_GMAIL_API_KEY=your-secure-api-key-here

# Server settings
MCP_GMAIL_PORT=8090
MCP_GMAIL_HOST=0.0.0.0  # Accept external connections

# Gmail OAuth
MCP_GMAIL_CREDENTIALS_PATH=credentials.json
MCP_GMAIL_TOKEN_PATH=token.json
```

### Generate a Secure API Key

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Example output: `xK9mP2vL8nQ5rT7wY4zA1bC6dE3fG0hJ9iK2lM5nO8pQ`

## Manual Deployment

If you prefer to deploy manually instead of using the automated script:

### Step 1: Start the Secure Server

```bash
# Load environment variables (or use python-dotenv)
# Windows:
set MCP_GMAIL_API_KEY=your-key-here

# Linux/Mac:
export MCP_GMAIL_API_KEY=your-key-here

# Start the server
uv run python mcp_gmail/secure_server.py
```

### Step 2: Start ngrok

In a separate terminal:

```bash
ngrok http 8090
```

### Step 3: Get Your Public URL

ngrok will display a URL like:
```
Forwarding    https://abc123.ngrok.io -> http://localhost:8090
```

## Using the Deployed Server

### Health Check (No Authentication)

```bash
curl https://your-ngrok-url.ngrok.io/health
```

Expected response:
```json
{"status": "ok"}
```

### Authenticated Request

```bash
curl -H "X-API-Key: your-api-key-here" \
     https://your-ngrok-url.ngrok.io/sse
```

### From Python Client

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "https://your-ngrok-url.ngrok.io"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Health check
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# MCP request (requires authentication)
response = requests.post(
    f"{BASE_URL}/sse",
    headers=headers,
    json={"method": "tools/list"}
)
print(response.json())
```

### From Claude Desktop

Update your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gmail-remote": {
      "url": "https://your-ngrok-url.ngrok.io/sse",
      "headers": {
        "X-API-Key": "your-api-key-here"
      },
      "transport": "sse"
    }
  }
}
```

## Monitoring

### ngrok Dashboard

Access the ngrok web interface at [http://127.0.0.1:4040](http://127.0.0.1:4040) to:
- View all requests
- Inspect request/response details
- Replay requests
- Monitor traffic

### Server Logs

The deployment script shows server logs in real-time. Watch for:
- ✅ Successful authentication: `200` status codes
- ❌ Failed authentication: `401` (missing key) or `403` (invalid key)
- 📧 Gmail API calls

## Security Best Practices

### 1. Protect Your API Key

- ✅ Never commit `.env` to git (it's in `.gitignore`)
- ✅ Use environment variables in production
- ✅ Rotate keys regularly
- ✅ Use different keys for different environments

### 2. Use ngrok Security Features

For production, consider ngrok's paid features:
- **Custom domains**: Use your own domain instead of random URLs
- **IP whitelisting**: Restrict access to specific IPs
- **OAuth**: Add OAuth layer on top of API key

```bash
# Example: ngrok with IP whitelisting
ngrok http 8090 --cidr-allow 1.2.3.4/32
```

### 3. Monitor Access

- Review ngrok dashboard regularly
- Check for unusual request patterns
- Set up alerts for failed authentication attempts

### 4. Gmail API Quotas

Be aware of Gmail API quotas:
- 1 billion quota units per day
- 250 quota units per user per second
- Most operations cost 5-10 units

Monitor usage at: [https://console.cloud.google.com/apis/api/gmail.googleapis.com/metrics](https://console.cloud.google.com/apis/api/gmail.googleapis.com/metrics)

## Troubleshooting

### "Missing API key" Error

**Problem**: Requests return 401 error
```json
{"error": "Missing API key", "message": "Please provide API key in X-API-Key header"}
```

**Solution**: Add the `X-API-Key` header to your request:
```bash
curl -H "X-API-Key: your-key" https://your-url.ngrok.io/health
```

### "Invalid API key" Error

**Problem**: Requests return 403 error
```json
{"error": "Invalid API key", "message": "The provided API key is invalid"}
```

**Solution**:
1. Check your `.env` file for the correct API key
2. Ensure the key matches exactly (no extra spaces)
3. Restart the server after changing `.env`

### ngrok Not Found

**Problem**: `deploy_ngrok.py` fails with "ngrok is not installed"

**Solution**:
1. Download ngrok from [https://ngrok.com/download](https://ngrok.com/download)
2. Extract and add to PATH
3. Authenticate: `ngrok authtoken YOUR_TOKEN`

### Server Won't Start

**Problem**: Server fails to start or exits immediately

**Solution**:
1. Check that `credentials.json` exists
2. Verify Gmail API is enabled in Google Cloud Console
3. Check server logs for specific errors
4. Ensure port 8090 is not already in use

### Connection Refused

**Problem**: Can't connect to ngrok URL

**Solution**:
1. Verify server is running (`http://localhost:8090/health`)
2. Check ngrok is running (`http://127.0.0.1:4040`)
3. Ensure `MCP_GMAIL_HOST=0.0.0.0` in `.env`
4. Check firewall settings

## Production Deployment

For production use, consider:

### 1. Use a Persistent ngrok Domain

```bash
# With ngrok paid plan
ngrok http 8090 --domain=your-domain.ngrok.app
```

### 2. Use a Process Manager

Keep the server running with `systemd` or `supervisor`:

```ini
# /etc/systemd/system/mcp-gmail.service
[Unit]
Description=Gmail MCP Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/mcp-gmail-main
Environment="MCP_GMAIL_API_KEY=your-key"
ExecStart=/usr/bin/python3 mcp_gmail/secure_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. Use Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install uv && uv sync

ENV MCP_GMAIL_HOST=0.0.0.0
ENV MCP_GMAIL_PORT=8090

CMD ["uv", "run", "python", "mcp_gmail/secure_server.py"]
```

### 4. Use a Reverse Proxy

For production, use nginx or Caddy instead of ngrok:

```nginx
# nginx configuration
server {
    listen 443 ssl;
    server_name mcp.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Cost Considerations

### ngrok Pricing

- **Free**: 1 online endpoint, random URLs, 40 connections/min
- **Personal ($8/mo)**: Custom domains, more endpoints
- **Production**: Higher limits, SLA

### Gmail API

- Free tier is generous (1B quota units/day)
- Typical email operations: 5-10 units each
- Monitor at Google Cloud Console

## Next Steps

After deploying:

1. ✅ Test the `/health` endpoint
2. ✅ Test authenticated endpoints with your API key
3. ✅ Connect from your client application
4. ✅ Set up monitoring and logging
5. ✅ Plan for production deployment if needed

## Support

If you encounter issues:

1. Check server logs
2. Review ngrok dashboard at `http://127.0.0.1:4040`
3. Verify Gmail API quotas
4. Test with curl/Postman before client integration
