"""Base interface for sandbox backends."""

from abc import ABC, abstractmethod


class SandboxBackend(ABC):
    """Base class for platform-specific sandbox backends."""

    @property
    @abstractmethod
    def agent_url(self) -> str:
        """URL for the sandbox agent API.

        Returns:
            Base URL for the agent (e.g., "http://localhost:9000")
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is available on this system.

        Returns:
            True if backend can be used
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the sandbox infrastructure is currently running.

        Returns:
            True if the agent is running
        """
        pass

    @abstractmethod
    def ensure_running(self) -> None:
        """Ensure the sandbox infrastructure is running.

        This should:
        1. Create necessary resources if they don't exist
        2. Start the agent if it's not running
        3. Wait for the agent to be ready

        Raises:
            SandboxStartupError: If unable to start the infrastructure
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the sandbox infrastructure."""
        pass

    @abstractmethod
    def destroy(self) -> None:
        """Completely destroy the sandbox infrastructure."""
        pass
