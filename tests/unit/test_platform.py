"""Tests for platform detection."""

from unittest.mock import patch

import pytest

from pctx_sandbox.exceptions import PlatformNotSupportedError
from pctx_sandbox.platform import detect_platform, get_backend


class TestDetectPlatform:
    """Tests for detect_platform function."""

    def test_detects_darwin(self):
        """Should detect macOS platform."""
        with patch("sys.platform", "darwin"):
            assert detect_platform() == "darwin"

    def test_detects_linux(self):
        """Should detect Linux platform."""
        with patch("sys.platform", "linux"):
            assert detect_platform() == "linux"

    def test_detects_win32(self):
        """Should detect Windows platform."""
        with patch("sys.platform", "win32"):
            assert detect_platform() == "win32"


class TestGetBackend:
    """Tests for get_backend function."""

    def test_returns_lima_backend_on_darwin(self):
        """Should return LimaBackend on macOS."""
        with patch("sys.platform", "darwin"):
            with patch("pctx_sandbox.platform.lima.LimaBackend.is_available", return_value=True):
                backend = get_backend()
                assert backend.__class__.__name__ == "LimaBackend"

    def test_raises_on_linux(self):
        """Should raise PlatformNotSupportedError on Linux (not yet implemented)."""
        with patch("sys.platform", "linux"):
            with pytest.raises(PlatformNotSupportedError) as exc_info:
                get_backend()
            assert "Linux support is not yet implemented" in str(exc_info.value)
            assert "firejail/bubblewrap" in str(exc_info.value)

    def test_raises_on_windows(self):
        """Should raise PlatformNotSupportedError on Windows (not yet implemented)."""
        with patch("sys.platform", "win32"):
            with pytest.raises(PlatformNotSupportedError) as exc_info:
                get_backend()
            assert "Windows support is not yet implemented" in str(exc_info.value)
            assert "WSL2" in str(exc_info.value)
