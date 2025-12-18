"""Platform detection and backend selection."""

import sys
from pathlib import Path
from typing import Literal

from .base import SandboxBackend
from .lima import LimaBackend
from .native import NativeBackend
from .wsl2 import WSL2Backend

PlatformType = Literal["darwin", "linux", "win32"]


def detect_platform() -> PlatformType:
    """Detect the current platform.

    Returns:
        Platform identifier: "darwin", "linux", or "win32"
    """
    return sys.platform  # type: ignore


def has_kvm_access() -> bool:
    """Check if KVM device is accessible.

    Returns:
        True if /dev/kvm exists and is accessible
    """
    return Path("/dev/kvm").exists()


def get_backend() -> SandboxBackend:
    """Get the appropriate sandbox backend for the current platform.

    Returns:
        Appropriate backend instance for the platform

    Raises:
        LimaNotInstalledError: On macOS without Lima installed
        PlatformNotSupportedError: On unsupported platforms (Linux/Windows)
    """
    platform = detect_platform()

    if platform == "darwin":
        # macOS: Use Lima for VM-level isolation (filesystem, env, resources)
        # Lima VM uses firejail inside for syscall restrictions
        # This provides defense-in-depth: VM isolation + process sandboxing
        from ..exceptions import LimaNotInstalledError
        from .lima import LimaBackend

        backend = LimaBackend()
        if not backend.is_available():
            raise LimaNotInstalledError(
                "Lima is not installed.\n\n"
                "Install Lima using Homebrew:\n"
                "  brew install lima\n\n"
                "Or visit: https://lima-vm.io/docs/installation/"
            )
        return backend

    elif platform == "linux":
        # TODO: Implement Linux support with native firejail/bubblewrap
        from ..exceptions import PlatformNotSupportedError

        raise PlatformNotSupportedError(
            "Linux support is not yet implemented.\n\n"
            "Planned implementation: Native firejail/bubblewrap sandboxing\n"
            "Track progress: https://github.com/portofcontext/python-sandbox/issues"
        )

    elif platform == "win32":
        # TODO: Implement Windows support with WSL2
        from ..exceptions import PlatformNotSupportedError

        raise PlatformNotSupportedError(
            "Windows support is not yet implemented.\n\n"
            "Planned implementation: WSL2 backend\n"
            "Track progress: https://github.com/portofcontext/python-sandbox/issues"
        )

    # Fallback for unknown platforms
    from ..exceptions import PlatformNotSupportedError

    raise PlatformNotSupportedError(
        f"Unsupported platform: {platform}\n\n"
        "Supported platforms: macOS (darwin)\n"
        "Coming soon: Linux, Windows"
    )


__all__ = [
    "detect_platform",
    "has_kvm_access",
    "get_backend",
    "SandboxBackend",
    "LimaBackend",
    "NativeBackend",
    "WSL2Backend",
]
