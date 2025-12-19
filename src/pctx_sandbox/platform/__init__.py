"""Platform detection and backend selection."""

from .base import SandboxBackend
from .podman import PodmanBackend


def get_backend() -> SandboxBackend:
    """Get the Podman sandbox backend.

    Returns:
        Podman backend instance

    Raises:
        PodmanNotInstalledError: If Podman is not installed
    """
    from ..exceptions import PodmanNotInstalledError

    backend: SandboxBackend = PodmanBackend()
    if not backend.is_available():
        raise PodmanNotInstalledError(
            "Podman is not installed.\n\n"
            "Install Podman:\n\n"
            "macOS:\n"
            "  brew install podman\n"
            "  podman machine init\n"
            "  podman machine start\n\n"
            "Linux (Debian/Ubuntu):\n"
            "  sudo apt-get update\n"
            "  sudo apt-get install podman\n\n"
            "Linux (Fedora/RHEL):\n"
            "  sudo dnf install podman\n\n"
            "Or visit: https://podman.io/docs/installation"
        )
    return backend


__all__ = [
    "get_backend",
    "SandboxBackend",
    "PodmanBackend",
]
