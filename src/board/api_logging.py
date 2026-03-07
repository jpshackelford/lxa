"""API request/response logging for debugging and fixture generation.

When enabled via LXA_LOG_API=1 or config, logs each REST/GraphQL
call and its response to separate files with incrementing numbers.

Files are saved to ~/.lxa/api_logs/ by default, or to LXA_LOG_API_DIR.

File naming:
- Request:  {sequence:04d}_request.json
- Response: {sequence:04d}_response.json

Each file includes metadata (timestamp, method, url, headers) plus body.
"""

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Thread-safe counter for sequence numbers
_sequence_lock = threading.Lock()
_sequence_counter = 0


def _get_next_sequence() -> int:
    """Get next sequence number (thread-safe)."""
    global _sequence_counter
    with _sequence_lock:
        _sequence_counter += 1
        return _sequence_counter


def _reset_sequence() -> None:
    """Reset sequence counter (for testing)."""
    global _sequence_counter
    with _sequence_lock:
        _sequence_counter = 0


def is_api_logging_enabled() -> bool:
    """Check if API logging is enabled via environment variable or config.

    Returns:
        True if LXA_LOG_API is set to a truthy value ("1", "true", "yes")
    """
    value = os.environ.get("LXA_LOG_API", "").lower()
    return value in ("1", "true", "yes", "on")


def get_log_directory() -> Path:
    """Get the directory for API logs.

    Returns:
        Path to log directory (default: ~/.lxa/api_logs/)
    """
    custom_dir = os.environ.get("LXA_LOG_API_DIR")
    if custom_dir:
        return Path(custom_dir)

    return Path.home() / ".lxa" / "api_logs"


def ensure_log_directory() -> Path:
    """Ensure log directory exists and return its path."""
    log_dir = get_log_directory()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _sanitize_headers(headers: httpx.Headers | dict) -> dict:
    """Sanitize headers by masking sensitive values.

    Args:
        headers: Original headers

    Returns:
        Headers dict with Authorization tokens masked
    """
    result = dict(headers)
    sensitive_keys = {"authorization", "x-github-token"}

    for key in list(result.keys()):
        if key.lower() in sensitive_keys:
            # Show token type but mask the actual token
            value = result[key]
            if isinstance(value, str):
                parts = value.split(" ", 1)
                if len(parts) == 2:
                    result[key] = f"{parts[0]} [REDACTED]"
                else:
                    result[key] = "[REDACTED]"
    return result


def log_request(request: httpx.Request) -> None:
    """Log an API request to a file.

    Args:
        request: The httpx Request object
    """
    if not is_api_logging_enabled():
        return

    try:
        log_dir = ensure_log_directory()
        seq = _get_next_sequence()

        # Store sequence on request for response correlation
        request.extensions["log_sequence"] = seq

        # Determine API type
        api_type = "graphql" if "/graphql" in str(request.url) else "rest"

        # Parse body (may be JSON for GraphQL)
        body = None
        if request.content:
            try:
                body = json.loads(request.content)
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = request.content.decode("utf-8", errors="replace")

        data = {
            "sequence": seq,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "api_type": api_type,
            "method": request.method,
            "url": str(request.url),
            "headers": _sanitize_headers(request.headers),
            "body": body,
        }

        filename = f"{seq:04d}_request.json"
        filepath = log_dir / filename

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug("Logged API request to %s", filepath)

    except Exception as e:
        logger.warning("Failed to log API request: %s", e)


def log_response(response: httpx.Response) -> None:
    """Log an API response to a file.

    Args:
        response: The httpx Response object
    """
    if not is_api_logging_enabled():
        return

    try:
        log_dir = ensure_log_directory()

        # Get sequence from request extension
        seq = response.request.extensions.get("log_sequence")
        if seq is None:
            # Fallback if request wasn't logged
            seq = _get_next_sequence()

        # Determine API type
        api_type = "graphql" if "/graphql" in str(response.url) else "rest"

        # Parse response body
        body = None
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            body = response.text

        data = {
            "sequence": seq,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "api_type": api_type,
            "status_code": response.status_code,
            "url": str(response.url),
            "headers": dict(response.headers),
            "body": body,
        }

        filename = f"{seq:04d}_response.json"
        filepath = log_dir / filename

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug("Logged API response to %s", filepath)

    except Exception as e:
        logger.warning("Failed to log API response: %s", e)


class LoggingTransport(httpx.BaseTransport):
    """Transport wrapper that logs requests and responses.

    This wraps the default transport to intercept and log all
    HTTP traffic when API logging is enabled.
    """

    def __init__(self, transport: httpx.BaseTransport | None = None):
        """Initialize with underlying transport.

        Args:
            transport: The underlying transport (default: HTTPTransport)
        """
        self._transport = transport or httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a request, logging it and the response.

        Args:
            request: The request to send

        Returns:
            The response
        """
        # Log request before sending
        log_request(request)

        # Send request using underlying transport
        response = self._transport.handle_request(request)

        # Read response body to enable logging (httpx streams by default)
        response.read()

        # Log response
        log_response(response)

        return response

    def close(self) -> None:
        """Close the underlying transport."""
        self._transport.close()


def create_logging_client(
    headers: dict | None = None,
    timeout: float = 30.0,
    **kwargs,
) -> httpx.Client:
    """Create an httpx Client with logging enabled.

    This is a convenience function to create a properly configured
    client with the logging transport when API logging is enabled.

    Args:
        headers: Request headers
        timeout: Request timeout in seconds
        **kwargs: Additional arguments passed to httpx.Client

    Returns:
        Configured httpx.Client
    """
    if is_api_logging_enabled():
        transport = LoggingTransport()
        return httpx.Client(
            headers=headers,
            timeout=timeout,
            transport=transport,
            **kwargs,
        )
    else:
        return httpx.Client(
            headers=headers,
            timeout=timeout,
            **kwargs,
        )


def clear_logs() -> int:
    """Clear all logged API files.

    Returns:
        Number of files deleted
    """
    log_dir = get_log_directory()
    if not log_dir.exists():
        return 0

    count = 0
    for f in log_dir.glob("*.json"):
        try:
            f.unlink()
            count += 1
        except OSError as e:
            logger.warning("Failed to delete %s: %s", f, e)

    _reset_sequence()
    return count
