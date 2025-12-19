"""Tests for Native backend."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from pctx_sandbox.exceptions import SandboxStartupError
from pctx_sandbox.platform.native import NativeBackend


class TestNativeBackend:
    """Tests for NativeBackend class."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        backend = NativeBackend()
        assert backend.agent_url == "http://localhost:9000"
        assert backend.AGENT_PORT == 9000
        assert backend.PID_FILE == Path("/tmp/pctx-sandbox-agent.pid")
        assert backend.CACHE_DIR == Path("/tmp/pctx-sandbox-cache")

    def test_is_available_when_nsjail_installed_and_python_310(self):
        """Should return True when nsjail is in PATH and Python >= 3.10."""
        backend = NativeBackend()
        with (
            patch("shutil.which", return_value="/usr/local/bin/nsjail"),
            patch("sys.version_info", (3, 10, 0)),
        ):
            assert backend.is_available() is True

    def test_is_available_when_nsjail_not_installed(self):
        """Should return False when nsjail is not in PATH."""
        backend = NativeBackend()
        with patch("shutil.which", return_value=None):
            assert backend.is_available() is False

    def test_is_available_when_python_version_too_old(self):
        """Should return False when Python < 3.10."""
        backend = NativeBackend()
        with (
            patch("shutil.which", return_value="/usr/local/bin/nsjail"),
            patch("sys.version_info", (3, 9, 0)),
        ):
            assert backend.is_available() is False

    def test_is_running_when_pid_file_exists_and_process_alive_and_healthy(self):
        """Should return True when PID file exists, process is alive, and health check passes."""
        backend = NativeBackend()
        mock_pid_file = Mock()
        mock_pid_file.exists.return_value = True
        mock_pid_file.read_text.return_value = "12345"

        with (
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("os.kill") as mock_kill,
            patch("httpx.get") as mock_httpx_get,
        ):
            mock_kill.return_value = None  # Process exists
            mock_response = Mock()
            mock_response.status_code = 200
            mock_httpx_get.return_value = mock_response

            assert backend.is_running() is True

    def test_is_running_when_pid_file_exists_but_process_dead(self):
        """Should return False and clean up stale PID file when process doesn't exist."""
        backend = NativeBackend()
        mock_pid_file = Mock()
        mock_pid_file.exists.return_value = True
        mock_pid_file.read_text.return_value = "12345"

        with (
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("os.kill", side_effect=OSError("No such process")),
        ):
            assert backend.is_running() is False
            mock_pid_file.unlink.assert_called_once()

    def test_is_running_when_pid_file_exists_but_health_check_fails(self):
        """Should return False and clean up PID file when health check fails."""
        backend = NativeBackend()
        mock_pid_file = Mock()
        mock_pid_file.exists.return_value = True
        mock_pid_file.read_text.return_value = "12345"

        with (
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("os.kill") as mock_kill,
            patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")),
        ):
            mock_kill.return_value = None  # Process exists

            assert backend.is_running() is False
            mock_pid_file.unlink.assert_called_once()

    def test_is_running_when_no_pid_file_but_health_check_succeeds(self):
        """Should return True when health check succeeds even without PID file."""
        backend = NativeBackend()
        mock_pid_file = Mock()
        mock_pid_file.exists.return_value = False

        with (
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("httpx.get") as mock_httpx_get,
        ):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_httpx_get.return_value = mock_response

            assert backend.is_running() is True

    def test_is_running_when_no_pid_file_and_health_check_fails(self):
        """Should return False when no PID file and health check fails."""
        backend = NativeBackend()
        mock_pid_file = Mock()
        mock_pid_file.exists.return_value = False

        with (
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")),
        ):
            assert backend.is_running() is False

    def test_ensure_running_does_nothing_when_already_running(self):
        """Should not start agent when already running."""
        backend = NativeBackend()
        with (
            patch.object(backend, "is_running", return_value=True),
            patch("subprocess.Popen") as mock_popen,
        ):
            backend.ensure_running()
            mock_popen.assert_not_called()

    def test_ensure_running_starts_agent_when_not_running(self):
        """Should start agent process when not running."""
        backend = NativeBackend()
        mock_proc = Mock()
        mock_proc.pid = 12345

        mock_cache_dir = Mock()
        mock_log_file = Mock()
        # Make CACHE_DIR / "agent.log" return mock_log_file
        mock_cache_dir.__truediv__ = Mock(return_value=mock_log_file)
        mock_pid_file = Mock()

        with (
            patch.object(backend, "is_running", return_value=False),
            patch.object(backend, "CACHE_DIR", mock_cache_dir),
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("pctx_sandbox.platform.native.SandboxClient") as mock_client_class,
            patch("builtins.open", create=True),
        ):
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            backend.ensure_running()

            # Should create cache directory
            mock_cache_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

            # Should start agent process
            mock_popen.assert_called_once()
            args = mock_popen.call_args
            assert sys.executable in args[0][0]
            assert "simple_agent.py" in str(args[0][0])

            # Should write PID file
            mock_pid_file.write_text.assert_called_once_with("12345")

            # Should wait for health check
            mock_client.wait_for_healthy.assert_called_once_with(max_wait=30)

    def test_ensure_running_cleans_up_pid_file_on_failure(self):
        """Should clean up PID file if agent startup fails."""
        backend = NativeBackend()
        mock_proc = Mock()
        mock_proc.pid = 12345

        mock_cache_dir = Mock()
        mock_pid_file = Mock()
        mock_pid_file.exists.return_value = True

        with (
            patch.object(backend, "is_running", return_value=False),
            patch.object(backend, "CACHE_DIR", mock_cache_dir),
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("subprocess.Popen", return_value=mock_proc),
            patch("pctx_sandbox.platform.native.SandboxClient") as mock_client_class,
            patch("builtins.open", create=True),
        ):
            mock_client = Mock()
            mock_client.wait_for_healthy.side_effect = Exception("Health check failed")
            mock_client_class.return_value = mock_client

            with pytest.raises(SandboxStartupError):
                backend.ensure_running()

            # Should clean up PID file on failure
            mock_pid_file.unlink.assert_called_once()

    def test_ensure_running_raises_when_agent_script_not_found(self):
        """Should raise SandboxStartupError when agent script doesn't exist."""
        backend = NativeBackend()
        mock_cache_dir = Mock()

        with (
            patch.object(backend, "is_running", return_value=False),
            patch.object(backend, "CACHE_DIR", mock_cache_dir),
            patch("pathlib.Path.exists", return_value=False),
        ):
            with pytest.raises(SandboxStartupError, match="Agent script not found"):
                backend.ensure_running()

    def test_stop_when_no_pid_file(self):
        """Should do nothing when PID file doesn't exist."""
        backend = NativeBackend()
        mock_pid_file = Mock()
        mock_pid_file.exists.return_value = False

        with (
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("os.kill") as mock_kill,
        ):
            backend.stop()
            mock_kill.assert_not_called()

    def test_stop_sends_sigterm_and_waits(self):
        """Should send SIGTERM and wait for graceful shutdown."""
        backend = NativeBackend()
        mock_pid_file = Mock()
        mock_pid_file.exists.side_effect = [True, True]  # Exists, then still exists at cleanup
        mock_pid_file.read_text.return_value = "12345"

        with (
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("os.kill") as mock_kill,
            patch("time.sleep"),
        ):
            # First call to check if alive, then raises OSError (process dead)
            mock_kill.side_effect = [None, OSError("No such process")]

            backend.stop()

            # Should send SIGTERM
            assert any(
                call[0] == (12345, 15)  # 15 is SIGTERM
                for call in mock_kill.call_args_list
            )

            # Should clean up PID file
            mock_pid_file.unlink.assert_called_once()

    def test_stop_sends_sigkill_if_process_doesnt_terminate(self):
        """Should send SIGKILL if process doesn't terminate gracefully."""
        backend = NativeBackend()
        mock_pid_file = Mock()
        mock_pid_file.exists.side_effect = [True, True]
        mock_pid_file.read_text.return_value = "12345"

        with (
            patch.object(backend, "PID_FILE", mock_pid_file),
            patch("os.kill") as mock_kill,
            patch("time.sleep"),
        ):
            # Process stays alive through all checks (50 iterations), then gets SIGKILL
            backend.stop()

            # Should eventually send SIGKILL
            assert any(
                call[0] == (12345, 9)  # 9 is SIGKILL
                for call in mock_kill.call_args_list
            )

    def test_destroy_stops_agent_and_removes_cache(self):
        """Should stop agent and remove cache directory."""
        backend = NativeBackend()
        mock_cache_dir = Mock()
        mock_cache_dir.exists.return_value = True

        with (
            patch.object(backend, "stop") as mock_stop,
            patch.object(backend, "CACHE_DIR", mock_cache_dir),
            patch("shutil.rmtree") as mock_rmtree,
        ):
            backend.destroy()

            mock_stop.assert_called_once()
            mock_rmtree.assert_called_once_with(mock_cache_dir)

    def test_destroy_handles_missing_cache_dir(self):
        """Should handle case where cache directory doesn't exist."""
        backend = NativeBackend()
        mock_cache_dir = Mock()
        mock_cache_dir.exists.return_value = False

        with (
            patch.object(backend, "stop") as mock_stop,
            patch.object(backend, "CACHE_DIR", mock_cache_dir),
            patch("shutil.rmtree") as mock_rmtree,
        ):
            backend.destroy()

            mock_stop.assert_called_once()
            mock_rmtree.assert_not_called()
