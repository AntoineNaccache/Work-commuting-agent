"""
Deploy MCP Gmail & Calendar Server via ngrok with Bearer token authentication.

This script:
1. Generates a secure bearer token (or uses existing one)
2. Starts the MCP server with authentication wrapper
3. Deploys via ngrok
4. Displays connection information for Telnyx integration

Usage:
    python deploy_ngrok.py [--port PORT] [--regenerate-token]
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mcp_gmail.secure_wrapper import generate_bearer_token, create_secure_app
from mcp_gmail.server import mcp
import uvicorn


def load_or_create_token(token_file: Path, regenerate: bool = False) -> str:
    """Load existing bearer token or create a new one."""
    if token_file.exists() and not regenerate:
        with open(token_file, "r") as f:
            token = f.read().strip()
            print(f"[OK] Using existing bearer token from {token_file}")
            return token
    else:
        token = generate_bearer_token()
        with open(token_file, "w") as f:
            f.write(token)
        print(f"[OK] Generated new bearer token and saved to {token_file}")
        return token


def start_ngrok_tunnel(port: int):
    """Start ngrok tunnel and return the public URL."""
    try:
        from pyngrok import ngrok
    except ImportError:
        print("\n[ERROR] pyngrok not installed")
        print("Install it with: pip install pyngrok")
        print("Or with uv: uv pip install pyngrok")
        sys.exit(1)

    # Start ngrok tunnel
    print(f"\n[*] Starting ngrok tunnel on port {port}...")
    try:
        tunnel = ngrok.connect(port, bind_tls=True)
        public_url = tunnel.public_url
        print(f"[OK] Ngrok tunnel established")
        return public_url
    except Exception as e:
        print(f"\n[ERROR] Error starting ngrok: {e}")
        print("\nMake sure:")
        print("1. ngrok is installed (https://ngrok.com/download)")
        print("2. You have an ngrok account and authtoken configured")
        print("   Run: ngrok config add-authtoken <your-token>")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Deploy MCP server via ngrok")
    parser.add_argument("--port", type=int, default=8090, help="Port to run server on (default: 8090)")
    parser.add_argument(
        "--regenerate-token",
        action="store_true",
        help="Generate a new bearer token (replaces existing)"
    )
    parser.add_argument(
        "--no-ngrok",
        action="store_true",
        help="Run server without ngrok (local only)"
    )
    args = parser.parse_args()

    # Paths
    project_dir = Path(__file__).parent
    token_file = project_dir / ".bearer_token"

    # Load or create bearer token
    bearer_token = load_or_create_token(token_file, args.regenerate_token)

    # Create secured app using the SSE app from FastMCP
    print("[OK] Creating secure MCP server wrapper...")
    secured_app = create_secure_app(mcp.sse_app(), bearer_token)

    # Start ngrok if requested
    ngrok_url = None
    if not args.no_ngrok:
        ngrok_url = start_ngrok_tunnel(args.port)

    # Display connection information
    print("\n" + "=" * 70)
    print("*** MCP SERVER READY FOR TELNYX INTEGRATION ***")
    print("=" * 70)

    if ngrok_url:
        print(f"\n>> Public URL (use this in Telnyx):")
        print(f"   {ngrok_url}")
        print(f"\n   Note: In Telnyx, use: {ngrok_url}/sse")
    else:
        print(f"\n>> Local URL:")
        print(f"   http://localhost:{args.port}")

    print(f"\n>> Bearer Token (use this as API Key in Telnyx):")
    print(f"   {bearer_token}")

    print(f"\n>> Telnyx Configuration:")
    print(f"   Name: Gmail Calendar MCP")
    print(f"   Type: SSE")
    if ngrok_url:
        print(f"   URL: {ngrok_url}/sse")
    else:
        print(f"   URL: http://localhost:{args.port}/sse")
    print(f"   API Key: {bearer_token}")

    print(f"\n>> How to configure in Telnyx:")
    print(f"   1. In the 'Create MCP Server' dialog:")
    print(f"   2. Set Name: Gmail Calendar MCP")
    print(f"   3. Set Type: SSE (not HTTP)")
    if ngrok_url:
        print(f"   4. Set URL: {ngrok_url}/sse")
    else:
        print(f"   4. Set URL: http://localhost:{args.port}/sse")
    print(f"   5. Click '+ Append integration secret'")
    print(f"   6. Paste the bearer token above")

    print(f"\n>> Health check:")
    if ngrok_url:
        print(f"   {ngrok_url}/health (no auth required)")
    else:
        print(f"   http://localhost:{args.port}/health (no auth required)")

    print("\n" + "=" * 70)
    print("\n[!] Keep this terminal open to maintain the ngrok tunnel")
    print("Press Ctrl+C to stop the server\n")

    # Start the server
    try:
        uvicorn.run(
            secured_app,
            host="0.0.0.0",  # Allow external connections via ngrok
            port=args.port,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down server...")
        if ngrok_url:
            from pyngrok import ngrok
            ngrok.disconnect(ngrok_url)
            print("[OK] Ngrok tunnel closed")
    finally:
        if ngrok_url:
            try:
                from pyngrok import ngrok
                ngrok.kill()
            except:
                pass


if __name__ == "__main__":
    main()
