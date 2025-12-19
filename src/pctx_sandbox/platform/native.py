"""Native Linux backend using nsjail directly on the host."""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from pctx_sandbox.client import SandboxClient
from pctx_sandbox.exceptions import SandboxStartupError

from .base import SandboxBackend


class NativeBackend(SandboxBackend):
    """Native Linux backend with direct nsjail sandboxing (no VM layer)."""

    AGENT_PORT = 9000
    PID_FILE = Path("/tmp/pctx-sandbox-agent.pid")
    CACHE_DIR = Path("/tmp/pctx-sandbox-cache")

    def __init__(self) -> None:
        """Initialize the native backend."""
        self._agent_url = f"http://localhost:{self.AGENT_PORT}"

    @property
    def agent_url(self) -> str:
        """Get the agent URL."""
        return self._agent_url

    def is_available(self) -> bool:
        """Check if native backend can be used (nsjail installed, Python 3.10+)."""
        # Check for nsjail binary
        if not shutil.which("nsjail"):
            return False

        # Check Python version
        if sys.version_info < (3, 10):  # noqa: UP036
            return False

        return True

    def is_running(self) -> bool:
        """Check if the sandbox agent is running."""
        # Method 1: Check PID file
        if self.PID_FILE.exists():
            try:
                pid = int(self.PID_FILE.read_text().strip())
                # Check if process exists
                try:
                    # Sending signal 0 doesn't actually send a signal, just checks if process exists
                    os.kill(pid, 0)

                    # Process exists, verify it's our agent by checking if port is listening
                    try:
                        response = httpx.get(f"{self.agent_url}/health", timeout=1.0)
                        return response.status_code == 200
                    except httpx.ConnectError:
                        # PID exists but agent not responding, stale PID file
                        self.PID_FILE.unlink()
                        return False
                except OSError:
                    # Process doesn't exist, stale PID file
                    self.PID_FILE.unlink()
                    return False
            except (ValueError, OSError):
                return False

        # Method 2: Try health check directly
        try:
            response = httpx.get(f"{self.agent_url}/health", timeout=1.0)
            return response.status_code == 200
        except httpx.ConnectError:
            return False

    def ensure_running(self) -> None:
        """Ensure the sandbox agent is running."""
        if self.is_running():
            return

        # Create cache directory if it doesn't exist
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Start agent as background daemon
        agent_script = Path(__file__).parent.parent / "agent" / "simple_agent.py"

        if not agent_script.exists():
            raise SandboxStartupError(f"Agent script not found at {agent_script}")

        try:
            # Start agent process with output redirected
            log_file = self.CACHE_DIR / "agent.log"
            with open(log_file, "w") as log:
                proc = subprocess.Popen(
                    [sys.executable, str(agent_script)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from parent process
                    cwd=str(agent_script.parent),
                    env={
                        **os.environ,
                        "PCTX_CACHE_DIR": str(self.CACHE_DIR),
                    },
                )

            # Write PID file
            self.PID_FILE.write_text(str(proc.pid))

            # Wait for agent to become healthy
            client = SandboxClient(self.agent_url)
            client.wait_for_healthy(max_wait=30)

        except Exception as e:
            # Cleanup on failure
            if self.PID_FILE.exists():
                self.PID_FILE.unlink()
            raise SandboxStartupError(f"Failed to start agent: {e}") from e

    def stop(self) -> None:
        """Stop the sandbox agent."""
        if not self.PID_FILE.exists():
            return

        try:
            pid = int(self.PID_FILE.read_text().strip())
            # Try graceful shutdown first (SIGTERM)
            try:
                os.kill(pid, signal.SIGTERM)

                # Wait up to 5 seconds for graceful shutdown
                for _ in range(50):
                    try:
                        os.kill(pid, 0)  # Check if still exists
                        time.sleep(0.1)
                    except OSError:
                        break  # Process terminated
                else:
                    # Force kill if still running
                    os.kill(pid, signal.SIGKILL)
            except OSError:
                pass  # Process already dead
        except (ValueError, OSError):
            pass
        finally:
            if self.PID_FILE.exists():
                self.PID_FILE.unlink()

    def destroy(self) -> None:
        """Destroy the sandbox infrastructure completely."""
        # Stop the agent
        self.stop()

        # Remove cache directory
        if self.CACHE_DIR.exists():
            import shutil

            shutil.rmtree(self.CACHE_DIR)
