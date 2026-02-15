"""Request tracking and logging middleware."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import (
    channel_var,
    get_logger,
    request_id_var,
    session_id_var,
    user_id_var,
)

logger = get_logger("app.middleware")


def determine_channel(path: str) -> str:
    """Determine the logging channel based on request path.

    Args:
        path: Request URL path.

    Returns:
        Channel name for logging.
    """
    if path.startswith("/api/query") or path.startswith("/api/chat"):
        return "query"
    elif path.startswith("/api/contracts"):
        return "contracts"
    elif path.startswith("/api/auth"):
        return "auth"
    elif path.startswith("/api/dashboard"):
        return "dashboard"
    elif path.startswith("/api/audit"):
        return "audit"
    elif path.startswith("/api/users") or path.startswith("/api/clients"):
        return "admin"
    elif path.startswith("/api/"):
        return "api"
    else:
        return "system"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request tracking and structured logging.

    Features:
    - Generates unique request ID for each request
    - Logs request start and completion
    - Tracks request duration
    - Propagates context variables (request_id, user_id, etc.)
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize middleware."""
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process the request with logging and tracking.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            HTTP response.
        """
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Set context variables
        request_id_token = request_id_var.set(request_id)
        channel_token = channel_var.set(determine_channel(request.url.path))

        # Extract user info from auth header if present (will be set properly after auth)
        user_id_token = None
        session_id_token = None

        # Check for session ID in headers or cookies
        session_id = request.headers.get("X-Session-ID") or request.cookies.get("session_id")
        if session_id:
            session_id_token = session_id_var.set(session_id)

        # Record start time
        start_time = time.perf_counter()

        # Log request start
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else None

        logger.info(
            f"Request started: {method} {path}",
            method=method,
            path=path,
            query=query,
            client_ip=_get_client_ip(request),
        )

        try:
            # Process the request
            response = await call_next(request)

            # Calculate duration
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Log request completion
            logger.info(
                f"Request completed: {method} {path} → {response.status_code} ({duration_ms}ms)",
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration even for errors
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Log the error
            logger.error(
                f"Request failed: {method} {path} ({duration_ms}ms)",
                method=method,
                path=path,
                duration_ms=duration_ms,
                error=str(e),
                exc_info=True,
            )
            raise

        finally:
            # Reset context variables
            request_id_var.reset(request_id_token)
            channel_var.reset(channel_token)
            if user_id_token:
                user_id_var.reset(user_id_token)
            if session_id_token:
                session_id_var.reset(session_id_token)


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP from request headers.

    Args:
        request: FastAPI request object.

    Returns:
        Client IP address or None.
    """
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return None


def set_user_context(user_id: str, session_id: str | None = None) -> None:
    """Set user context for logging.

    Call this after authentication to associate logs with a user.

    Args:
        user_id: Authenticated user's ID.
        session_id: Optional session ID.
    """
    user_id_var.set(user_id)
    if session_id:
        session_id_var.set(session_id)
