"""Tests for Podman backend."""

from unittest.mock import Mock, patch

import httpx
import pytest

from pctx_sandbox.exceptions import SandboxStartupError
from pctx_sandbox.platform.podman import PodmanBackend


class TestPodmanBackend:
    """Tests for PodmanBackend class."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        backend = PodmanBackend()
        assert backend.agent_url == "http://localhost:9000"
        assert backend.AGENT_PORT == 9000
        assert backend.CONTAINER_NAME == "pctx-sandbox-agent"
        assert backend.IMAGE_NAME == "pctx-sandbox-agent"
        assert backend.cpus == 4
        assert backend.memory_gb == 4

    def test_initialization_with_custom_resources(self):
        """Should initialize with custom resource limits."""
        backend = PodmanBackend(cpus=2, memory_gb=2)
        assert backend.cpus == 2
        assert backend.memory_gb == 2

    def test_is_available_when_podman_installed(self):
        """Should return True when podman is in PATH."""
        backend = PodmanBackend()
        with patch("shutil.which", return_value="/usr/bin/podman"):
            assert backend.is_available() is True

    def test_is_available_when_podman_not_installed(self):
        """Should return False when podman is not in PATH."""
        backend = PodmanBackend()
        with patch("shutil.which", return_value=None):
            assert backend.is_available() is False

    def test_is_running_when_container_running_and_healthy(self):
        """Should return True when container is running and health check passes."""
        backend = PodmanBackend()
        mock_result = Mock()
        mock_result.stdout = "abc123\n"
        mock_result.returncode = 0

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("httpx.get") as mock_httpx_get,
        ):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_httpx_get.return_value = mock_response

            assert backend.is_running() is True

    def test_is_running_when_container_not_running(self):
        """Should return False when container is not running."""
        backend = PodmanBackend()
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            assert backend.is_running() is False

    def test_is_running_when_health_check_fails(self):
        """Should return False when health check fails."""
        backend = PodmanBackend()
        mock_result = Mock()
        mock_result.stdout = "abc123\n"
        mock_result.returncode = 0

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")),
        ):
            assert backend.is_running() is False

    def test_ensure_running_does_nothing_when_already_running(self):
        """Should not start container when already running."""
        backend = PodmanBackend()
        with (
            patch.object(backend, "is_running", return_value=True),
            patch.object(backend, "_ensure_image") as mock_ensure_image,
            patch.object(backend, "_start_container") as mock_start_container,
        ):
            backend.ensure_running()
            mock_ensure_image.assert_not_called()
            mock_start_container.assert_not_called()

    def test_ensure_running_starts_container_when_not_running(self):
        """Should build image and start container when not running."""
        backend = PodmanBackend()
        with (
            patch.object(backend, "is_running", return_value=False),
            patch.object(backend, "_ensure_image") as mock_ensure_image,
            patch.object(backend, "_start_container") as mock_start_container,
            patch("pctx_sandbox.platform.podman.SandboxClient") as mock_client_class,
        ):
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            backend.ensure_running()

            mock_ensure_image.assert_called_once()
            mock_start_container.assert_called_once()
            mock_client.wait_for_healthy.assert_called_once_with(max_wait=60)

    def test_ensure_image_builds_when_not_exists(self):
        """Should build image when it doesn't exist."""
        backend = PodmanBackend()

        # Mock image check (no image)
        mock_check_result = Mock()
        mock_check_result.stdout = ""
        mock_check_result.returncode = 0

        # Mock build success
        mock_build_result = Mock()
        mock_build_result.returncode = 0

        with patch(
            "subprocess.run", side_effect=[mock_check_result, mock_build_result]
        ) as mock_run:
            backend._ensure_image()

            # Should call podman build
            build_call = mock_run.call_args_list[1]
            assert "podman" in build_call[0][0]
            assert "build" in build_call[0][0]

    def test_ensure_image_skips_when_exists(self):
        """Should skip build when image already exists."""
        backend = PodmanBackend()

        # Mock image check (image exists)
        mock_result = Mock()
        mock_result.stdout = "abc123\n"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend._ensure_image()

            # Should only check, not build
            assert mock_run.call_count == 1

    def test_ensure_image_raises_when_dockerfile_not_found(self):
        """Should raise SandboxStartupError when Dockerfile doesn't exist."""
        backend = PodmanBackend()

        # Mock image check (no image)
        mock_check_result = Mock()
        mock_check_result.stdout = ""
        mock_check_result.returncode = 0

        with (
            patch("subprocess.run", return_value=mock_check_result),
            patch("pathlib.Path.exists", return_value=False),
        ):
            with pytest.raises(SandboxStartupError, match="Dockerfile not found"):
                backend._ensure_image()

    def test_start_container_starts_with_correct_options(self):
        """Should start container with correct resource limits and ports."""
        backend = PodmanBackend(cpus=4, memory_gb=8)

        # Mock rm, cgroup check, and run
        mock_rm_result = Mock()
        mock_cgroup_result = Mock()
        mock_cgroup_result.returncode = 0  # cgroup controllers available
        mock_run_result = Mock()
        mock_run_result.returncode = 0

        with patch(
            "subprocess.run", side_effect=[mock_rm_result, mock_cgroup_result, mock_run_result]
        ) as mock_run:
            backend._start_container()

            # Check run command (third call)
            run_call = mock_run.call_args_list[2]
            cmd = run_call[0][0]

            assert "podman" in cmd
            assert "run" in cmd
            assert "-d" in cmd
            assert "--memory" in cmd
            assert "8g" in cmd
            assert "--cpus" in cmd
            assert "4" in cmd
            assert "-p" in cmd
            assert "9000:9000" in cmd

    def test_stop_stops_container(self):
        """Should stop the container."""
        backend = PodmanBackend()

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            backend.stop()

            cmd = mock_run.call_args[0][0]
            assert "podman" in cmd
            assert "stop" in cmd
            assert backend.CONTAINER_NAME in cmd

    def test_destroy_removes_container_and_image(self):
        """Should remove container and image."""
        backend = PodmanBackend()

        with patch("subprocess.run") as mock_run:
            backend.destroy()

            # Should call podman rm and podman rmi
            assert mock_run.call_count >= 2

            # Check for rm and rmi commands
            calls = [str(call[0][0]) for call in mock_run.call_args_list]
            assert any("rm" in call for call in calls)
            assert any("rmi" in call for call in calls)
