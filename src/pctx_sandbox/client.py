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
                r = self._http.get(f"{self.base_url}/health")
                if r.status_code == 200:
                    return
            except httpx.ConnectError:
                pass
            time.sleep(0.5)
        raise SandboxStartupError(f"Agent not healthy after {max_wait}s")

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a sandboxed function synchronously.

        Args:
            payload: Dictionary containing function, args, and configuration

        Returns:
            Result dictionary from the sandbox
        """
        timeout_sec = payload.get("timeout_sec", 30)
        request_timeout = timeout_sec + 5  # Buffer for overhead

        response = self._http.post(
            f"{self.base_url}/execute",
            content=msgpack.packb(payload),
            headers={"Content-Type": "application/msgpack"},
            timeout=request_timeout,
        )
        return msgpack.unpackb(response.content)

    async def execute_async(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a sandboxed function asynchronously.

        Args:
            payload: Dictionary containing function, args, and configuration

        Returns:
            Result dictionary from the sandbox
        """
        # Create a new AsyncClient for each request to avoid event loop issues
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            timeout_sec = payload.get("timeout_sec", 30)
            request_timeout = timeout_sec + 5

            response = await client.post(
                f"{self.base_url}/execute",
                content=msgpack.packb(payload),
                headers={"Content-Type": "application/msgpack"},
                timeout=request_timeout,
            )
            return msgpack.unpackb(response.content)
