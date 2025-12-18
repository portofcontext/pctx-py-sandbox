"""Tests for Lima backend."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from pctx_sandbox.exceptions import SandboxStartupError
from pctx_sandbox.platform.lima import LimaBackend


class TestLimaBackend:
    """Tests for LimaBackend class."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        backend = LimaBackend()
        assert backend.agent_url == "http://localhost:9000"
        assert backend.VM_NAME == "pctx-sandbox"
        assert backend.AGENT_PORT == 9000

    def test_is_available_when_lima_installed(self):
        """Should return True when limactl is in PATH."""
        backend = LimaBackend()
        with patch("shutil.which", return_value="/usr/local/bin/limactl"):
            assert backend.is_available() is True

    def test_is_available_when_lima_not_installed(self):
        """Should return False when limactl is not in PATH."""
        backend = LimaBackend()
        with patch("shutil.which", return_value=None):
            assert backend.is_available() is False

    def test_is_running_when_vm_running(self):
        """Should return True when VM is running."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"name": "pctx-sandbox", "status": "Running"}])

        with patch("subprocess.run", return_value=mock_result):
            assert backend.is_running() is True

    def test_is_running_when_vm_stopped(self):
        """Should return False when VM is stopped."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"name": "pctx-sandbox", "status": "Stopped"}])

        with patch("subprocess.run", return_value=mock_result):
            assert backend.is_running() is False

    def test_is_running_when_vm_not_exists(self):
        """Should return False when VM doesn't exist."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([])

        with patch("subprocess.run", return_value=mock_result):
            assert backend.is_running() is False

    def test_is_running_when_limactl_fails(self):
        """Should return False when limactl command fails."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            assert backend.is_running() is False

    def test_vm_exists_when_vm_exists(self):
        """Should return True when VM exists (any state)."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"name": "pctx-sandbox", "status": "Stopped"}])

        with patch("subprocess.run", return_value=mock_result):
            assert backend.vm_exists() is True

    def test_vm_exists_when_vm_not_exists(self):
        """Should return False when VM doesn't exist."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"name": "other-vm", "status": "Running"}])

        with patch("subprocess.run", return_value=mock_result):
            assert backend.vm_exists() is False

    def test_ensure_running_creates_vm_when_not_exists(self):
        """Should create VM when it doesn't exist."""
        backend = LimaBackend()
        with (
            patch.object(backend, "is_available", return_value=True),
            patch.object(backend, "vm_exists", return_value=False),
            patch.object(backend, "_create_vm") as mock_create,
            patch.object(backend, "is_running", return_value=True),
        ):
            backend.ensure_running()
            mock_create.assert_called_once()

    def test_ensure_running_starts_vm_when_stopped(self):
        """Should start VM when it exists but is stopped."""
        backend = LimaBackend()
        with (
            patch.object(backend, "is_available", return_value=True),
            patch.object(backend, "vm_exists", return_value=True),
            patch.object(backend, "is_running", side_effect=[False, True]),
            patch.object(backend, "_start_vm") as mock_start,
        ):
            backend.ensure_running()
            mock_start.assert_called_once()

    def test_ensure_running_does_nothing_when_already_running(self):
        """Should not create or start VM when already running."""
        backend = LimaBackend()
        with (
            patch.object(backend, "is_available", return_value=True),
            patch.object(backend, "vm_exists", return_value=True),
            patch.object(backend, "is_running", return_value=True),
            patch.object(backend, "_create_vm") as mock_create,
            patch.object(backend, "_start_vm") as mock_start,
        ):
            backend.ensure_running()
            mock_create.assert_not_called()
            mock_start.assert_not_called()

    def test_create_vm_calls_limactl_create(self):
        """Should call limactl create with correct arguments."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0

        with (
            patch("subprocess.run", return_value=mock_result) as mock_run,
            patch.object(backend, "_start_vm"),
        ):
            backend._create_vm()

            # Check that limactl create was called
            args = mock_run.call_args[0][0]
            assert "limactl" in args
            assert "create" in args
            assert "--name" in args
            assert "pctx-sandbox" in args

    def test_start_vm_calls_limactl_start(self):
        """Should call limactl start with VM name."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend._start_vm()

            args = mock_run.call_args[0][0]
            assert "limactl" in args
            assert "start" in args
            assert "pctx-sandbox" in args

    def test_start_vm_raises_on_failure(self):
        """Should raise SandboxStartupError when start fails."""
        backend = LimaBackend()
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "limactl")):
            with pytest.raises(SandboxStartupError):
                backend._start_vm()

    def test_stop_calls_limactl_stop(self):
        """Should call limactl stop with VM name."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.stop()

            args = mock_run.call_args[0][0]
            assert "limactl" in args
            assert "stop" in args
            assert "pctx-sandbox" in args

    def test_destroy_calls_limactl_delete(self):
        """Should call limactl delete with force flag."""
        backend = LimaBackend()
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.destroy()

            args = mock_run.call_args[0][0]
            assert "limactl" in args
            assert "delete" in args
            assert "--force" in args
            assert "pctx-sandbox" in args
