"""pctx-sandbox: Execute Python functions in isolated Firecracker microVMs."""

from .decorator import sandbox, sandbox_async
from .exceptions import (
    DependencyInstallError,
    KVMNotAvailableError,
    LimaNotInstalledError,
    PlatformNotSupportedError,
    SandboxError,
    SandboxExecutionError,
    SandboxStartupError,
    SandboxTimeoutError,
    SerializationError,
)

__version__ = "0.1.0"
__all__ = [
    "sandbox",
    "sandbox_async",
    "SandboxError",
    "SandboxStartupError",
    "SandboxExecutionError",
    "SandboxTimeoutError",
    "SerializationError",
    "DependencyInstallError",
    "PlatformNotSupportedError",
    "LimaNotInstalledError",
    "KVMNotAvailableError",
]
