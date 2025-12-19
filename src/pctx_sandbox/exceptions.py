"""Exception classes for pctx-sandbox."""


class SandboxError(Exception):
    """Base exception for sandbox errors."""

    pass


class SandboxStartupError(SandboxError):
    """Failed to start sandbox infrastructure."""

    pass


class SandboxExecutionError(SandboxError):
    """Error during sandboxed execution."""

    def __init__(
        self,
        message: str,
        error_type: str | None = None,
        traceback_str: str | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Error message
            error_type: Type of the original error
            traceback_str: Traceback from the sandboxed execution
        """
        super().__init__(message)
        self.error_type = error_type
        self.traceback_str = traceback_str


class SandboxTimeoutError(SandboxError):
    """Execution exceeded timeout."""

    pass


class SerializationError(SandboxError):
    """Failed to serialize/deserialize function or result."""

    pass


class DependencyInstallError(SandboxError):
    """Failed to install dependencies in sandbox."""

    pass


class PlatformNotSupportedError(SandboxError):
    """Platform not supported for sandboxing."""

    pass


class PodmanNotInstalledError(PlatformNotSupportedError):
    """Podman not installed."""

    pass
