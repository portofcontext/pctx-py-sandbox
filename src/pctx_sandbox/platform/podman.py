"""Podman backend for container-based sandboxing."""

import os
import shutil
import subprocess
from pathlib import Path

import httpx

from pctx_sandbox.client import SandboxClient
from pctx_sandbox.exceptions import SandboxStartupError

from .base import SandboxBackend


class PodmanBackend(SandboxBackend):
    """Podman-based backend using rootless containers."""

    CONTAINER_NAME = "pctx-sandbox-agent"
    IMAGE_NAME = "pctx-sandbox-agent"
    AGENT_PORT = 9000

    def __init__(
        self,
        cpus: int | None = None,
        memory_gb: int | None = None,
    ) -> None:
        """Initialize the Podman backend.

        Args:
            cpus: Number of CPUs for containers (default: 2, or PCTX_PODMAN_CPUS env var)
            memory_gb: Memory in GB (default: 2, or PCTX_PODMAN_MEMORY_GB env var)
        """
        self._agent_url = f"http://localhost:{self.AGENT_PORT}"
        self.cpus = cpus or int(os.getenv("PCTX_PODMAN_CPUS", "2"))
        self.memory_gb = memory_gb or int(os.getenv("PCTX_PODMAN_MEMORY_GB", "2"))

    @property
    def agent_url(self) -> str:
        """Get the agent URL."""
        return self._agent_url

    def is_available(self) -> bool:
        """Check if Podman is installed."""
        return shutil.which("podman") is not None

    def is_running(self) -> bool:
        """Check if the sandbox container is running."""
        result = subprocess.run(
            ["podman", "ps", "--filter", f"name={self.CONTAINER_NAME}", "--format", "{{.ID}}"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return False

        container_id = result.stdout.strip()
        if not container_id:
            return False

        # Verify agent is healthy
        try:
            response = httpx.get(f"{self.agent_url}/health", timeout=1.0)
            return response.status_code == 200
        except httpx.ConnectError:
            return False

    def ensure_running(self) -> None:
        """Ensure the sandbox container is running."""
        if self.is_running():
            return

        # Build image if needed
        self._ensure_image()

        # Start container
        self._start_container()

        # Wait for agent to be healthy
        client = SandboxClient(self.agent_url)
        client.wait_for_healthy(max_wait=60)

    def _ensure_image(self) -> None:
        """Ensure the agent container image exists."""
        # Check if image exists
        result = subprocess.run(
            ["podman", "images", "--filter", f"reference={self.IMAGE_NAME}", "--format", "{{.ID}}"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            return

        # Build image
        dockerfile_path = Path(__file__).parent / "Dockerfile.agent"
        agent_dir = Path(__file__).parent.parent / "agent"

        if not dockerfile_path.exists():
            raise SandboxStartupError(f"Dockerfile not found at {dockerfile_path}")

        # Create temporary empty auth file to disable credential helpers
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"auths":{}}')
            authfile_path = f.name

        try:
            subprocess.run(
                [
                    "podman",
                    "build",
                    f"--authfile={authfile_path}",  # Use empty auth file
                    "-t",
                    self.IMAGE_NAME,
                    "-f",
                    str(dockerfile_path),
                    str(agent_dir.parent),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise SandboxStartupError(
                f"Failed to build Podman image: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}"
            ) from e
        finally:
            # Clean up temp file
            Path(authfile_path).unlink(missing_ok=True)

    def _start_container(self) -> None:
        """Start the agent container."""
        # Remove old container if it exists
        subprocess.run(
            ["podman", "rm", "-f", self.CONTAINER_NAME],
            capture_output=True,
        )

        # Create cache directory in home directory (works across platforms)
        cache_dir = Path.home() / ".pctx-sandbox-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Create temporary empty auth file to disable credential helpers
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"auths":{}}')
            authfile_path = f.name

        # Start new container
        try:
            subprocess.run(
                [
                    "podman",
                    "run",
                    "-d",
                    f"--authfile={authfile_path}",  # Use empty auth file
                    "--name",
                    self.CONTAINER_NAME,
                    "--memory",
                    f"{self.memory_gb}g",
                    "--cpus",
                    str(self.cpus),
                    "-p",
                    f"{self.AGENT_PORT}:{self.AGENT_PORT}",
                    # Mount cache directory for dependency caching
                    "-v",
                    f"{cache_dir}:/tmp/pctx-cache",
                    # Security options for rootless containers
                    "--security-opt",
                    "label=disable",
                    self.IMAGE_NAME,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise SandboxStartupError(
                f"Failed to start Podman container: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}"
            ) from e
        finally:
            # Clean up temp file
            Path(authfile_path).unlink(missing_ok=True)

    def stop(self) -> None:
        """Stop the sandbox container."""
        subprocess.run(
            ["podman", "stop", self.CONTAINER_NAME],
            capture_output=True,
        )

    def destroy(self) -> None:
        """Destroy the sandbox container and image."""
        # Stop and remove container
        subprocess.run(
            ["podman", "rm", "-f", self.CONTAINER_NAME],
            capture_output=True,
        )

        # Remove image
        subprocess.run(
            ["podman", "rmi", "-f", self.IMAGE_NAME],
            capture_output=True,
        )

        # Remove cache directory
        cache_dir = Path.home() / ".pctx-sandbox-cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
