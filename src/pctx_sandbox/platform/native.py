"""Native Linux backend using Firecracker directly."""

from .base import SandboxBackend


class NativeBackend(SandboxBackend):
    """Native Linux backend with direct Firecracker access."""

    AGENT_PORT = 9000

    def __init__(self) -> None:
        """Initialize the native backend."""
        self._agent_url = f"http://localhost:{self.AGENT_PORT}"

    @property
    def agent_url(self) -> str:
        """Get the agent URL."""
        return self._agent_url

    def is_available(self) -> bool:
        """Check if native backend is available."""
        return True

    def is_running(self) -> bool:
        """Check if the sandbox agent is running."""
        raise NotImplementedError("Native backend not yet implemented")

    def ensure_running(self) -> None:
        """Ensure the sandbox agent is running."""
        raise NotImplementedError("Native backend not yet implemented")

    def stop(self) -> None:
        """Stop the sandbox agent."""
        raise NotImplementedError("Native backend not yet implemented")

    def destroy(self) -> None:
        """Destroy the sandbox infrastructure."""
        raise NotImplementedError("Native backend not yet implemented")
