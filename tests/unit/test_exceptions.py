"""Tests for exception classes."""

import pytest

from pctx_sandbox.exceptions import (
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


class TestSandboxError:
    """Tests for SandboxError base exception."""

    def test_is_exception(self):
        """SandboxError should be an Exception."""
        assert issubclass(SandboxError, Exception)

    def test_can_be_raised(self):
        """SandboxError should be raisable."""
        with pytest.raises(SandboxError) as exc_info:
            raise SandboxError("test error")
        assert str(exc_info.value) == "test error"


class TestSandboxStartupError:
    """Tests for SandboxStartupError."""

    def test_inherits_from_sandbox_error(self):
        """SandboxStartupError should inherit from SandboxError."""
        assert issubclass(SandboxStartupError, SandboxError)

    def test_can_be_raised_with_message(self):
        """SandboxStartupError should be raisable with a message."""
        with pytest.raises(SandboxStartupError) as exc_info:
            raise SandboxStartupError("Failed to start")
        assert str(exc_info.value) == "Failed to start"


class TestSandboxExecutionError:
    """Tests for SandboxExecutionError."""

    def test_inherits_from_sandbox_error(self):
        """SandboxExecutionError should inherit from SandboxError."""
        assert issubclass(SandboxExecutionError, SandboxError)

    def test_can_be_raised_with_message_only(self):
        """SandboxExecutionError should work with just a message."""
        with pytest.raises(SandboxExecutionError) as exc_info:
            raise SandboxExecutionError("Execution failed")
        assert str(exc_info.value) == "Execution failed"

    def test_stores_error_type(self):
        """SandboxExecutionError should store error_type attribute."""
        error = SandboxExecutionError("test", error_type="ValueError")
        assert error.error_type == "ValueError"

    def test_stores_traceback(self):
        """SandboxExecutionError should store traceback_str attribute."""
        traceback = "Traceback (most recent call last):\n  File..."
        error = SandboxExecutionError("test", traceback_str=traceback)
        assert error.traceback_str == traceback

    def test_optional_attributes_default_to_none(self):
        """SandboxExecutionError attributes should default to None."""
        error = SandboxExecutionError("test")
        assert error.error_type is None
        assert error.traceback_str is None


class TestSandboxTimeoutError:
    """Tests for SandboxTimeoutError."""

    def test_inherits_from_sandbox_error(self):
        """SandboxTimeoutError should inherit from SandboxError."""
        assert issubclass(SandboxTimeoutError, SandboxError)

    def test_can_be_raised(self):
        """SandboxTimeoutError should be raisable."""
        with pytest.raises(SandboxTimeoutError) as exc_info:
            raise SandboxTimeoutError("Execution timed out")
        assert "timed out" in str(exc_info.value)


class TestSerializationError:
    """Tests for SerializationError."""

    def test_inherits_from_sandbox_error(self):
        """SerializationError should inherit from SandboxError."""
        assert issubclass(SerializationError, SandboxError)

    def test_can_be_raised(self):
        """SerializationError should be raisable."""
        with pytest.raises(SerializationError) as exc_info:
            raise SerializationError("Failed to serialize")
        assert "serialize" in str(exc_info.value)


class TestDependencyInstallError:
    """Tests for DependencyInstallError."""

    def test_inherits_from_sandbox_error(self):
        """DependencyInstallError should inherit from SandboxError."""
        assert issubclass(DependencyInstallError, SandboxError)

    def test_can_be_raised(self):
        """DependencyInstallError should be raisable."""
        with pytest.raises(DependencyInstallError) as exc_info:
            raise DependencyInstallError("Failed to install pandas")
        assert "pandas" in str(exc_info.value)


class TestPlatformNotSupportedError:
    """Tests for PlatformNotSupportedError."""

    def test_inherits_from_sandbox_error(self):
        """PlatformNotSupportedError should inherit from SandboxError."""
        assert issubclass(PlatformNotSupportedError, SandboxError)

    def test_can_be_raised(self):
        """PlatformNotSupportedError should be raisable."""
        with pytest.raises(PlatformNotSupportedError) as exc_info:
            raise PlatformNotSupportedError("Platform not supported")
        assert "not supported" in str(exc_info.value)


class TestLimaNotInstalledError:
    """Tests for LimaNotInstalledError."""

    def test_inherits_from_platform_not_supported(self):
        """LimaNotInstalledError should inherit from PlatformNotSupportedError."""
        assert issubclass(LimaNotInstalledError, PlatformNotSupportedError)

    def test_can_be_raised(self):
        """LimaNotInstalledError should be raisable."""
        with pytest.raises(LimaNotInstalledError) as exc_info:
            raise LimaNotInstalledError("Lima not installed")
        assert "Lima" in str(exc_info.value)


class TestKVMNotAvailableError:
    """Tests for KVMNotAvailableError."""

    def test_inherits_from_platform_not_supported(self):
        """KVMNotAvailableError should inherit from PlatformNotSupportedError."""
        assert issubclass(KVMNotAvailableError, PlatformNotSupportedError)

    def test_can_be_raised(self):
        """KVMNotAvailableError should be raisable."""
        with pytest.raises(KVMNotAvailableError) as exc_info:
            raise KVMNotAvailableError("KVM not available")
        assert "KVM" in str(exc_info.value)
