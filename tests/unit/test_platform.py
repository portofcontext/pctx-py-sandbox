"""Tests for platform backend."""

from unittest.mock import patch

import pytest

from pctx_sandbox.exceptions import PodmanNotInstalledError
from pctx_sandbox.platform import get_backend
from pctx_sandbox.platform.podman import PodmanBackend


class TestGetBackend:
    """Tests for get_backend function."""

    def test_returns_podman_backend_when_available(self):
        """Should return PodmanBackend when Podman is available."""
        with patch("pctx_sandbox.platform.podman.PodmanBackend.is_available", return_value=True):
            backend = get_backend()
            assert isinstance(backend, PodmanBackend)

    def test_raises_when_podman_not_available(self):
        """Should raise PodmanNotInstalledError when Podman is not available."""
        with patch("pctx_sandbox.platform.podman.PodmanBackend.is_available", return_value=False):
            with pytest.raises(PodmanNotInstalledError) as exc_info:
                get_backend()
            assert "Podman is not installed" in str(exc_info.value)
            assert "brew install podman" in str(exc_info.value)
