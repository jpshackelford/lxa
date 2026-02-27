"""Tests for API request/response logging."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from src.board.api_logging import (
    LoggingTransport,
    _reset_sequence,
    _sanitize_headers,
    clear_logs,
    create_logging_client,
    get_log_directory,
    is_api_logging_enabled,
    log_request,
    log_response,
)


class TestApiLoggingEnabled:
    """Tests for is_api_logging_enabled()."""

    def test_disabled_by_default(self):
        """API logging is disabled when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LXA_LOG_API", None)
            assert is_api_logging_enabled() is False

    def test_enabled_with_1(self):
        """API logging is enabled when LXA_LOG_API=1."""
        with patch.dict(os.environ, {"LXA_LOG_API": "1"}):
            assert is_api_logging_enabled() is True

    def test_enabled_with_true(self):
        """API logging is enabled when LXA_LOG_API=true."""
        with patch.dict(os.environ, {"LXA_LOG_API": "true"}):
            assert is_api_logging_enabled() is True

    def test_enabled_with_yes(self):
        """API logging is enabled when LXA_LOG_API=yes."""
        with patch.dict(os.environ, {"LXA_LOG_API": "yes"}):
            assert is_api_logging_enabled() is True

    def test_enabled_with_on(self):
        """API logging is enabled when LXA_LOG_API=on."""
        with patch.dict(os.environ, {"LXA_LOG_API": "ON"}):
            assert is_api_logging_enabled() is True

    def test_disabled_with_0(self):
        """API logging is disabled when LXA_LOG_API=0."""
        with patch.dict(os.environ, {"LXA_LOG_API": "0"}):
            assert is_api_logging_enabled() is False

    def test_disabled_with_false(self):
        """API logging is disabled when LXA_LOG_API=false."""
        with patch.dict(os.environ, {"LXA_LOG_API": "false"}):
            assert is_api_logging_enabled() is False


class TestLogDirectory:
    """Tests for get_log_directory()."""

    def test_default_directory(self):
        """Default log directory is ~/.lxa/api_logs/."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LXA_LOG_API_DIR", None)
            result = get_log_directory()
            assert result == Path.home() / ".lxa" / "api_logs"

    def test_custom_directory(self):
        """Custom log directory via LXA_LOG_API_DIR."""
        with patch.dict(os.environ, {"LXA_LOG_API_DIR": "/tmp/my_logs"}):
            result = get_log_directory()
            assert result == Path("/tmp/my_logs")


class TestSanitizeHeaders:
    """Tests for header sanitization."""

    def test_masks_authorization_bearer(self):
        """Authorization header with Bearer token is masked."""
        headers = {"Authorization": "Bearer ghp_xxxxxxxxxxxxxxxxxxxx"}
        result = _sanitize_headers(headers)
        assert result["Authorization"] == "Bearer [REDACTED]"

    def test_masks_authorization_token(self):
        """Authorization header with token is masked."""
        headers = {"Authorization": "token abc123"}
        result = _sanitize_headers(headers)
        assert result["Authorization"] == "token [REDACTED]"

    def test_preserves_other_headers(self):
        """Non-sensitive headers are preserved."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "test",
        }
        result = _sanitize_headers(headers)
        assert result["Accept"] == "application/json"
        assert result["User-Agent"] == "test"

    def test_case_insensitive_matching(self):
        """Header matching is case-insensitive."""
        headers = {"AUTHORIZATION": "Bearer secret"}
        result = _sanitize_headers(headers)
        assert result["AUTHORIZATION"] == "Bearer [REDACTED]"


class TestLogRequestResponse:
    """Tests for logging requests and responses to files."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _reset_sequence()
            yield tmpdir

    def test_logs_request_when_enabled(self, temp_log_dir):
        """Request is logged to file when logging is enabled."""
        env = {"LXA_LOG_API": "1", "LXA_LOG_API_DIR": temp_log_dir}
        with patch.dict(os.environ, env):
            request = httpx.Request(
                "GET",
                "https://api.github.com/user",
                headers={"Authorization": "Bearer token123"},
            )
            log_request(request)

            log_path = Path(temp_log_dir) / "0001_request.json"
            assert log_path.exists()

            with open(log_path) as f:
                data = json.load(f)

            assert data["sequence"] == 1
            assert data["method"] == "GET"
            assert data["url"] == "https://api.github.com/user"
            assert data["api_type"] == "rest"
            assert "Bearer [REDACTED]" in data["headers"]["authorization"]

    def test_logs_graphql_request(self, temp_log_dir):
        """GraphQL request is logged with correct api_type."""
        env = {"LXA_LOG_API": "1", "LXA_LOG_API_DIR": temp_log_dir}
        with patch.dict(os.environ, env):
            request = httpx.Request(
                "POST",
                "https://api.github.com/graphql",
                json={"query": "{ viewer { login } }"},
            )
            log_request(request)

            log_path = Path(temp_log_dir) / "0001_request.json"
            with open(log_path) as f:
                data = json.load(f)

            assert data["api_type"] == "graphql"
            assert data["body"]["query"] == "{ viewer { login } }"

    def test_no_log_when_disabled(self, temp_log_dir):
        """No file is created when logging is disabled."""
        env = {"LXA_LOG_API": "0", "LXA_LOG_API_DIR": temp_log_dir}
        with patch.dict(os.environ, env):
            request = httpx.Request("GET", "https://api.github.com/user")
            log_request(request)

            files = list(Path(temp_log_dir).glob("*.json"))
            assert len(files) == 0

    def test_sequence_increments(self, temp_log_dir):
        """Sequence number increments with each request."""
        env = {"LXA_LOG_API": "1", "LXA_LOG_API_DIR": temp_log_dir}
        with patch.dict(os.environ, env):
            for i in range(3):
                request = httpx.Request("GET", f"https://api.github.com/test{i}")
                log_request(request)

            files = sorted(Path(temp_log_dir).glob("*_request.json"))
            assert len(files) == 3
            assert files[0].name == "0001_request.json"
            assert files[1].name == "0002_request.json"
            assert files[2].name == "0003_request.json"


class TestLoggingTransport:
    """Tests for the LoggingTransport wrapper."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _reset_sequence()
            yield tmpdir

    def test_logs_response_directly(self, temp_log_dir):
        """Response logging works when called directly."""
        env = {"LXA_LOG_API": "1", "LXA_LOG_API_DIR": temp_log_dir}
        with patch.dict(os.environ, env):
            # Create a mock request with sequence
            request = httpx.Request("GET", "https://api.github.com/user")
            request.extensions["log_sequence"] = 1

            # Create a mock response
            response = httpx.Response(
                200,
                json={"login": "testuser"},
                request=request,
            )

            log_response(response)

            # Check response log
            resp_path = Path(temp_log_dir) / "0001_response.json"
            assert resp_path.exists()

            with open(resp_path) as f:
                data = json.load(f)

            assert data["sequence"] == 1
            assert data["status_code"] == 200
            assert data["body"]["login"] == "testuser"

    def test_transport_wrapper_properties(self, temp_log_dir):
        """LoggingTransport wraps another transport."""
        transport = LoggingTransport()
        assert hasattr(transport, "_transport")
        assert hasattr(transport, "handle_request")
        assert hasattr(transport, "close")
        transport.close()


class TestClearLogs:
    """Tests for clear_logs()."""

    def test_clears_all_json_files(self):
        """Clears all JSON files in log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)

            # Create some log files
            (log_dir / "0001_request.json").write_text("{}")
            (log_dir / "0001_response.json").write_text("{}")
            (log_dir / "0002_request.json").write_text("{}")

            with patch.dict(os.environ, {"LXA_LOG_API_DIR": tmpdir}):
                count = clear_logs()

            assert count == 3
            assert len(list(log_dir.glob("*.json"))) == 0

    def test_returns_zero_for_nonexistent_dir(self):
        """Returns 0 when log directory doesn't exist."""
        with patch.dict(os.environ, {"LXA_LOG_API_DIR": "/nonexistent/path"}):
            count = clear_logs()
            assert count == 0


class TestCreateLoggingClient:
    """Tests for create_logging_client()."""

    def test_returns_regular_client_when_disabled(self):
        """Returns standard httpx.Client when logging disabled."""
        with patch.dict(os.environ, {"LXA_LOG_API": "0"}):
            client = create_logging_client()
            # Should be a regular client without logging transport
            assert isinstance(client, httpx.Client)
            client.close()

    def test_returns_logging_client_when_enabled(self):
        """Returns client with LoggingTransport when enabled."""
        with patch.dict(os.environ, {"LXA_LOG_API": "1"}):
            client = create_logging_client()
            assert isinstance(client, httpx.Client)
            # Transport should be LoggingTransport
            assert isinstance(client._transport, LoggingTransport)
            client.close()

    def test_passes_headers(self):
        """Headers are passed to the client."""
        with patch.dict(os.environ, {"LXA_LOG_API": "0"}):
            client = create_logging_client(headers={"X-Custom": "test"})
            assert client.headers.get("X-Custom") == "test"
            client.close()
