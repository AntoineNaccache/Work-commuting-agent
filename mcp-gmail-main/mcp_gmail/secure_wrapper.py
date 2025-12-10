"""
Secure wrapper for MCP server with Bearer token authentication.
This allows the server to be deployed via ngrok with API key protection for Telnyx.
"""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.routing import Route


class NgrokHostFixMiddleware(BaseHTTPMiddleware):
    """Middleware to fix ngrok host validation issues."""

    async def dispatch(self, request: Request, call_next):
        # Fix the Host header for ngrok tunnels to pass MCP's transport security validation
        # The MCP library validates the Host header, but ngrok uses random subdomains
        # We'll set it to localhost to pass validation
        if request.headers.get("host", "").endswith(".ngrok-free.app") or \
           request.headers.get("host", "").endswith(".ngrok-free.dev") or \
           request.headers.get("host", "").endswith(".ngrok.io"):
            # Create a mutable copy of the headers
            headers = dict(request.headers)
            headers["host"] = f"localhost:{request.url.port or 8090}"
            # Update the request scope
            request._headers = headers
            request.scope["headers"] = [
                (k.encode(), v.encode()) for k, v in headers.items()
            ]

        return await call_next(request)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Middleware to verify Bearer token on all requests except /health."""

    def __init__(self, app, bearer_token: str):
        super().__init__(app)
        self.bearer_token = bearer_token

    async def dispatch(self, request: Request, call_next):
        # Allow health check without authentication
        if request.url.path == "/health":
            return await call_next(request)

        # Verify Bearer token for all other endpoints
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return Response(
                content="Authorization header required",
                status_code=401,
                media_type="text/plain"
            )

        if not auth_header.startswith("Bearer "):
            return Response(
                content="Invalid authorization format. Use: Bearer <token>",
                status_code=401,
                media_type="text/plain"
            )

        provided_token = auth_header[7:]  # Remove "Bearer " prefix

        # Use secrets.compare_digest to prevent timing attacks
        if not secrets.compare_digest(provided_token, self.bearer_token):
            return Response(
                content="Invalid bearer token",
                status_code=403,
                media_type="text/plain"
            )

        # Token is valid, proceed with the request
        return await call_next(request)


def create_secure_app(mcp_sse_app, bearer_token: str):
    """
    Add Bearer token authentication middleware to the MCP SSE app.

    Args:
        mcp_sse_app: The MCP SSE Starlette application instance
        bearer_token: Bearer token for authentication

    Returns:
        Secured app with authentication middleware
    """
    # Define health check endpoint
    async def health_check(request):
        """Public health check endpoint (no auth required)."""
        return JSONResponse({"status": "healthy", "service": "MCP Gmail & Calendar Server"})

    # Add health check route
    mcp_sse_app.routes.insert(0, Route("/health", health_check, methods=["GET"]))

    # Add ngrok host fix middleware FIRST (before authentication)
    # This fixes the Host header validation issue with ngrok tunnels
    mcp_sse_app.add_middleware(NgrokHostFixMiddleware)

    # Add authentication middleware
    mcp_sse_app.add_middleware(BearerTokenMiddleware, bearer_token=bearer_token)

    return mcp_sse_app


def generate_bearer_token() -> str:
    """Generate a secure random bearer token."""
    return secrets.token_urlsafe(32)


if __name__ == "__main__":
    # Example: Generate a new bearer token
    print("Generated Bearer Token:")
    print(generate_bearer_token())
    print("\nSet this as MCP_BEARER_TOKEN environment variable")
