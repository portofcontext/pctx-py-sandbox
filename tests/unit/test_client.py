"""Tests for SandboxClient."""

from unittest.mock import Mock, patch

import httpx
import msgpack
import pytest

from pctx_sandbox.client import SandboxClient
from pctx_sandbox.exceptions import SandboxStartupError


class TestSandboxClient:
    """Tests for SandboxClient class."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        client = SandboxClient("http://localhost:9000")
        assert client.base_url == "http://localhost:9000"
        assert client.timeout == 30

    def test_initialization_with_custom_timeout(self):
        """Should accept custom timeout."""
        client = SandboxClient("http://localhost:9000", timeout=60)
        assert client.timeout == 60

    def test_wait_for_healthy_succeeds_immediately(self):
        """Should return immediately when agent is healthy."""
        client = SandboxClient("http://localhost:9000")
        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(client._http, "get", return_value=mock_response):
            client.wait_for_healthy(max_wait=5)

    def test_wait_for_healthy_retries_until_success(self):
        """Should retry until agent becomes healthy."""
        client = SandboxClient("http://localhost:9000")
        mock_response = Mock()
        mock_response.status_code = 200

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            return mock_response

        with patch.object(client._http, "get", side_effect=side_effect), patch("time.sleep"):
            client.wait_for_healthy(max_wait=5)
            assert call_count == 3

    def test_wait_for_healthy_raises_on_timeout(self):
        """Should raise SandboxStartupError after max_wait."""
        client = SandboxClient("http://localhost:9000")

        def side_effect(*args, **kwargs):
            raise httpx.ConnectError("Connection refused")

        with (
            patch.object(client._http, "get", side_effect=side_effect),
            patch("time.sleep"),
            patch("time.time", side_effect=[0, 0.5, 61]),
        ):
            with pytest.raises(SandboxStartupError) as exc_info:
                client.wait_for_healthy(max_wait=60)
            assert "not healthy" in str(exc_info.value)

    def test_execute_sends_correct_request(self):
        """Should send msgpack-encoded payload to /execute."""
        client = SandboxClient("http://localhost:9000")
        payload = {"fn_pickle": b"test", "args_pickle": b"args"}

        mock_response = Mock()
        mock_response.content = msgpack.packb({"success": True, "result_pickle": b"result"})

        with patch.object(client._http, "post", return_value=mock_response) as mock_post:
            result = client.execute(payload)

            # Check the POST was called correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://localhost:9000/execute"
            assert call_args[1]["headers"]["Content-Type"] == "application/msgpack"
            assert msgpack.unpackb(call_args[1]["content"]) == payload

            assert result == {"success": True, "result_pickle": b"result"}

    def test_execute_with_custom_timeout(self):
        """Should use payload timeout plus buffer."""
        client = SandboxClient("http://localhost:9000")
        payload = {"fn_pickle": b"test", "timeout_sec": 60}

        mock_response = Mock()
        mock_response.content = msgpack.packb({"success": True})

        with patch.object(client._http, "post", return_value=mock_response) as mock_post:
            client.execute(payload)

            call_args = mock_post.call_args
            # Should use 60 + 5 = 65 second timeout
            assert call_args[1]["timeout"] == 65

    def test_execute_with_default_timeout(self):
        """Should use default timeout when not specified in payload."""
        client = SandboxClient("http://localhost:9000")
        payload = {"fn_pickle": b"test"}

        mock_response = Mock()
        mock_response.content = msgpack.packb({"success": True})

        with patch.object(client._http, "post", return_value=mock_response) as mock_post:
            client.execute(payload)

            call_args = mock_post.call_args
            # Should use 30 + 5 = 35 second timeout
            assert call_args[1]["timeout"] == 35

    @pytest.mark.asyncio
    async def test_execute_async_sends_correct_request(self):
        """Should send async request correctly."""
        client = SandboxClient("http://localhost:9000")
        payload = {"fn_pickle": b"test", "is_async": True}

        mock_response = Mock()
        mock_response.content = msgpack.packb({"success": True, "result_pickle": b"result"})

        # Mock AsyncClient as context manager
        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            async def post(self, *args, **kwargs):
                return mock_response

        with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
            result = await client.execute_async(payload)
            assert result == {"success": True, "result_pickle": b"result"}

    @pytest.mark.asyncio
    async def test_execute_async_creates_new_client(self):
        """Should create new async http client for each request."""
        client = SandboxClient("http://localhost:9000")

        mock_response = Mock()
        mock_response.content = msgpack.packb({"success": True})

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            async def post(self, *args, **kwargs):
                return mock_response

        with patch("httpx.AsyncClient", return_value=MockAsyncClient()) as mock_client_class:
            await client.execute_async({"fn_pickle": b"test"})

            # AsyncClient should be created for the request
            mock_client_class.assert_called_once()
