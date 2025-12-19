"""Sandbox client for communicating with the sandbox agent."""

import time
from typing import Any

import httpx
import msgpack

from .exceptions import SandboxStartupError


class SandboxClient:
    """Client for communicating with the sandbox agent."""

    def __init__(self, base_url: str, timeout: int = 30) -> None:
        """Initialize the sandbox client.

        Args:
            base_url: Base URL for the sandbox agent API
            timeout: Default timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self._http = httpx.Client(timeout=timeout)

    def __del__(self) -> None:
        """Cleanup resources."""
        try:
            self._http.close()
        except Exception:
            pass

    def wait_for_healthy(self, max_wait: int = 60) -> None:
        """Wait for the sandbox agent to be ready.

        Args:
            max_wait: Maximum time to wait in seconds

        Raises:
            SandboxStartupError: If agent doesn't become healthy within max_wait
        """
        start = time.time()
        while time.time() - start < max_wait:
            try:
                r = self._http.get(f"{self.base_url}/health", timeout=1.0)
                if r.status_code == 200:
                    return
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
                # Handle connection refused, connection reset, and protocol errors during startup
                pass
            time.sleep(0.5)
        raise SandboxStartupError(f"Agent not healthy after {max_wait}s")

    def execute(self, payload: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
        """Execute a sandboxed function synchronously with retry logic.

        Args:
            payload: Dictionary containing function, args, and configuration
            max_retries: Maximum number of retry attempts for transient errors

        Returns:
            Result dictionary from the sandbox
        """
        timeout_sec = payload.get("timeout_sec", 30)
        request_timeout = timeout_sec + 5  # Buffer for overhead

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self._http.post(
                    f"{self.base_url}/execute",
                    content=msgpack.packb(payload),
                    headers={"Content-Type": "application/msgpack"},
                    timeout=request_timeout,
                )
                result = msgpack.unpackb(response.content)

                # Check if we got a transient worker error
                if result.get("error"):
                    error_type = result.get("error_type", "")
                    # Retry on worker-related transient errors
                    if error_type in ("ConnectionResetError", "WorkerUnresponsive", "WorkerDied"):
                        if attempt < max_retries - 1:
                            # Exponential backoff: 0.5s, 1s, 2s
                            backoff = 0.5 * (2**attempt)
                            time.sleep(backoff)
                            last_error = result
                            continue

                return result

            except (
                httpx.TimeoutException,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
            ):
                # Timeout errors - convert to proper error response
                return {
                    "error": True,
                    "error_type": "Timeout",
                    "error_message": f"Execution exceeded {timeout_sec}s timeout",
                }
            except Exception as e:
                # Network-level errors
                if attempt < max_retries - 1:
                    backoff = 0.1 * (2**attempt)
                    time.sleep(backoff)
                    last_error = {
                        "error": True,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    }
                    continue
                raise

        # If we exhausted retries, return the last error
        return last_error or {
            "error": True,
            "error_type": "MaxRetriesExceeded",
            "error_message": "Failed after maximum retries",
        }

    async def execute_async(self, payload: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
        """Execute a sandboxed function asynchronously with retry logic.

        Args:
            payload: Dictionary containing function, args, and configuration
            max_retries: Maximum number of retry attempts for transient errors

        Returns:
            Result dictionary from the sandbox
        """
        import asyncio

        timeout_sec = payload.get("timeout_sec", 30)
        request_timeout = timeout_sec + 5

        last_error = None
        for attempt in range(max_retries):
            try:
                # Create a new AsyncClient for each request to avoid event loop issues
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/execute",
                        content=msgpack.packb(payload),
                        headers={"Content-Type": "application/msgpack"},
                        timeout=request_timeout,
                    )
                    result = msgpack.unpackb(response.content)

                    # Check if we got a transient worker error
                    if result.get("error"):
                        error_type = result.get("error_type", "")
                        # Retry on worker-related transient errors
                        if error_type in (
                            "ConnectionResetError",
                            "WorkerUnresponsive",
                            "WorkerDied",
                        ):
                            if attempt < max_retries - 1:
                                # Exponential backoff: 0.5s, 1s, 2s
                                backoff = 0.5 * (2**attempt)
                                await asyncio.sleep(backoff)
                                last_error = result
                                continue

                    return result

            except (
                httpx.TimeoutException,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
            ):
                # Timeout errors - convert to proper error response
                return {
                    "error": True,
                    "error_type": "Timeout",
                    "error_message": f"Execution exceeded {timeout_sec}s timeout",
                }
            except Exception as e:
                # Network-level errors
                if attempt < max_retries - 1:
                    backoff = 0.1 * (2**attempt)
                    await asyncio.sleep(backoff)
                    last_error = {
                        "error": True,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    }
                    continue
                raise

        # If we exhausted retries, return the last error
        return last_error or {
            "error": True,
            "error_type": "MaxRetriesExceeded",
            "error_message": "Failed after maximum retries",
        }
