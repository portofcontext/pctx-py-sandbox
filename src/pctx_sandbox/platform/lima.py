"""Lima backend for macOS."""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from pctx_sandbox.client import SandboxClient
from pctx_sandbox.exceptions import SandboxStartupError

from .base import SandboxBackend

logger = logging.getLogger(__name__)


class LimaBackend(SandboxBackend):
    """Lima-based backend for macOS."""

    VM_NAME = "pctx-sandbox"
    AGENT_PORT = 9000

    def __init__(
        self,
        cpus: int | None = None,
        memory_gib: int | None = None,
        disk_gib: int | None = None,
    ) -> None:
        """Initialize the Lima backend.

        Args:
            cpus: Number of CPUs for the VM (default: 2, or PCTX_LIMA_CPUS env var)
            memory_gib: Memory in GiB (default: 4, or PCTX_LIMA_MEMORY_GIB env var)
            disk_gib: Disk size in GiB (default: 20, or PCTX_LIMA_DISK_GIB env var)
        """
        self._agent_url = f"http://localhost:{self.AGENT_PORT}"
        self._config_path = Path(__file__).parent / "lima-config.yaml"

        # Allow configuration via environment variables or parameters
        self.cpus = cpus or int(os.getenv("PCTX_LIMA_CPUS", "2"))
        self.memory_gib = memory_gib or int(os.getenv("PCTX_LIMA_MEMORY_GIB", "4"))
        self.disk_gib = disk_gib or int(os.getenv("PCTX_LIMA_DISK_GIB", "20"))

    @property
    def agent_url(self) -> str:
        """Get the agent URL."""
        return self._agent_url

    def is_available(self) -> bool:
        """Check if Lima is installed."""
        logger.debug("Checking if limactl is available")
        available = shutil.which("limactl") is not None
        logger.debug(f"limactl available: {available}")
        return available

    def is_running(self) -> bool:
        """Check if the sandbox VM is running."""
        logger.debug(f"Checking if VM '{self.VM_NAME}' is running")
        logger.debug("Running: limactl list --json")
        result = subprocess.run(["limactl", "list", "--json"], capture_output=True, text=True)
        logger.debug(f"limactl list returncode: {result.returncode}")

        if result.returncode != 0:
            logger.debug(f"limactl list failed with stderr: {result.stderr}")
            return False

        if not result.stdout.strip():
            logger.debug("limactl list returned empty output")
            return False

        logger.debug(f"limactl list output: {result.stdout}")
        data = json.loads(result.stdout)
        vms = [data] if isinstance(data, dict) else data
        logger.debug(f"Found {len(vms)} VM(s)")

        for vm in vms:
            logger.debug(f"VM: {vm['name']}, status: {vm['status']}")
            if vm["name"] == self.VM_NAME and vm["status"] == "Running":
                logger.debug(f"VM '{self.VM_NAME}' is running")
                return True

        logger.debug(f"VM '{self.VM_NAME}' is not running")
        return False

    def vm_exists(self) -> bool:
        """Check if the sandbox VM exists (running or stopped)."""
        logger.debug(f"Checking if VM '{self.VM_NAME}' exists")
        logger.debug("Running: limactl list --json")
        result = subprocess.run(["limactl", "list", "--json"], capture_output=True, text=True)
        logger.debug(f"limactl list returncode: {result.returncode}")

        if result.returncode != 0:
            logger.debug(f"limactl list failed with stderr: {result.stderr}")
            return False

        if not result.stdout.strip():
            logger.debug("limactl list returned empty output")
            return False

        logger.debug(f"limactl list output: {result.stdout}")
        data = json.loads(result.stdout)
        vms = [data] if isinstance(data, dict) else data
        exists = any(vm["name"] == self.VM_NAME for vm in vms)
        logger.debug(f"VM '{self.VM_NAME}' exists: {exists}")
        return exists

    def ensure_running(self) -> None:
        """Ensure the sandbox VM is created and running.

        Note: Lima availability is checked in get_backend() before this is called.
        """
        logger.debug(f"Ensuring VM '{self.VM_NAME}' is running")

        if not self.vm_exists():
            logger.debug("VM does not exist, creating...")
            self._create_vm()
        else:
            logger.debug("VM exists")

        if not self.is_running():
            logger.debug("VM is not running, starting...")
            self._start_vm()
        else:
            logger.debug("VM is already running")

        logger.debug("Starting agent inside VM")
        self._start_agent()

        logger.debug("Waiting for agent to be healthy")
        client = SandboxClient(self.agent_url)
        client.wait_for_healthy(max_wait=60)

    def _create_vm(self) -> None:
        """Create the Lima VM for sandbox agent."""
        cmd = [
            "limactl",
            "create",
            "--name",
            self.VM_NAME,
            f"--cpus={self.cpus}",
            f"--memory={self.memory_gib}",
            f"--disk={self.disk_gib}",
            str(self._config_path),
        ]
        logger.debug(f"Creating VM with command: {' '.join(cmd)}")
        logger.debug(f"Config path: {self._config_path}")
        logger.debug(f"Config exists: {self._config_path.exists()}")

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug("VM creation successful")
            if result.stdout:
                logger.debug(f"stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"stderr: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"VM creation failed with return code {e.returncode}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise

        logger.debug("Starting VM after creation")
        self._start_vm()

    def _start_vm(self) -> None:
        """Start the Lima VM."""
        logger.debug(f"Starting VM '{self.VM_NAME}'")
        logger.debug(f"Running: limactl start {self.VM_NAME}")

        try:
            result = subprocess.run(
                ["limactl", "start", self.VM_NAME],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug("VM start command completed successfully")
            if result.stdout:
                logger.debug(f"stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"stderr: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"VM start failed with return code {e.returncode}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            error_msg = f"Failed to start VM: {e}"
            if e.stderr:
                error_msg += f"\n\nLima error output:\n{e.stderr}"
            raise SandboxStartupError(error_msg) from e

    def stop(self) -> None:
        """Stop the sandbox VM."""
        logger.debug(f"Stopping VM '{self.VM_NAME}'")
        logger.debug(f"Running: limactl stop {self.VM_NAME}")
        result = subprocess.run(
            ["limactl", "stop", self.VM_NAME],
            capture_output=True,
            text=True,
        )
        logger.debug(f"Stop command completed with return code {result.returncode}")
        if result.stdout:
            logger.debug(f"stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"stderr: {result.stderr}")

    def destroy(self) -> None:
        """Destroy the sandbox VM completely."""
        logger.debug(f"Destroying VM '{self.VM_NAME}'")
        logger.debug(f"Running: limactl delete --force {self.VM_NAME}")
        result = subprocess.run(
            ["limactl", "delete", "--force", self.VM_NAME],
            capture_output=True,
            text=True,
        )
        logger.debug(f"Delete command completed with return code {result.returncode}")
        if result.stdout:
            logger.debug(f"stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"stderr: {result.stderr}")

    def _start_agent(self) -> None:
        """Start the agent inside the VM if not already running."""
        logger.debug("Checking if agent is already running")

        # First check if agent is already healthy
        try:
            import httpx

            response = httpx.get(f"{self.agent_url}/health", timeout=1.0)
            if response.status_code == 200:
                logger.debug("Agent is already running and healthy")
                return
        except httpx.ConnectError:
            logger.debug("Agent is not running, starting it")

        # Get the agent directory path
        agent_dir = Path(__file__).parent.parent / "agent"
        logger.debug(f"Agent directory: {agent_dir}")
        logger.debug(f"Agent directory exists: {agent_dir.exists()}")

        if not agent_dir.exists():
            raise SandboxStartupError(f"Agent directory not found at {agent_dir}")

        # Copy all agent files to VM
        logger.debug("Copying agent files to VM")
        agent_files = ["simple_agent.py", "pool.py", "worker.py", "nsjail.cfg"]
        for filename in agent_files:
            src_path = agent_dir / filename
            logger.debug(f"Copying {filename}")
            copy_cmd = ["limactl", "copy", str(src_path), f"{self.VM_NAME}:/tmp/{filename}"]
            result = subprocess.run(copy_cmd, capture_output=True, text=True)
            logger.debug(f"Copy {filename} return code: {result.returncode}")
            if result.returncode != 0:
                raise SandboxStartupError(f"Failed to copy {filename} to VM: {result.stderr}")

        # Fix file permissions for root access
        logger.debug("Setting file permissions for root access")
        chmod_cmd = [
            "limactl",
            "shell",
            self.VM_NAME,
            "sudo",
            "chmod",
            "644",
            "/tmp/simple_agent.py",
            "/tmp/pool.py",
            "/tmp/worker.py",
            "/tmp/nsjail.cfg",
        ]
        subprocess.run(chmod_cmd, capture_output=True, text=True)

        # Install agent dependencies system-wide (for root user)
        logger.debug("Installing agent dependencies in VM (system-wide)")
        install_cmd = [
            "limactl",
            "shell",
            self.VM_NAME,
            "sudo",
            "pip3",
            "install",
            "--quiet",
            "fastapi",
            "uvicorn",
            "cloudpickle",
            "msgpack",
        ]
        logger.debug(f"Running: {' '.join(install_cmd)}")
        result = subprocess.run(install_cmd, capture_output=True, text=True)
        logger.debug(f"Install command return code: {result.returncode}")
        if result.stdout:
            logger.debug(f"stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"stderr: {result.stderr}")

        if result.returncode != 0:
            raise SandboxStartupError(f"Failed to install agent dependencies: {result.stderr}")

        # Start the agent in the background as root (nsjail requires root for namespaces)
        logger.debug("Starting agent process in VM as root")
        # Must remove old log file first since it may be owned by regular user
        cleanup_cmd = ["limactl", "shell", self.VM_NAME, "sudo", "rm", "-f", "/tmp/agent.log"]
        subprocess.run(cleanup_cmd, capture_output=True, text=True)

        # Start agent as root with proper quoting - redirect must happen inside sudo
        start_cmd = [
            "limactl",
            "shell",
            self.VM_NAME,
            "sudo",
            "sh",
            "-c",
            "cd /tmp && nohup python3 simple_agent.py > agent.log 2>&1 & echo $!",
        ]
        logger.debug(f"Running: {' '.join(start_cmd)}")
        result = subprocess.run(start_cmd, capture_output=True, text=True)
        logger.debug(f"Start command return code: {result.returncode}")
        logger.debug(f"Agent PID: {result.stdout.strip()}")
        if result.stderr:
            logger.debug(f"stderr: {result.stderr}")

        if result.returncode != 0:
            # Check agent log for errors
            log_cmd = ["limactl", "shell", self.VM_NAME, "cat", "/tmp/agent.log"]
            log_result = subprocess.run(log_cmd, capture_output=True, text=True)
            error_msg = f"Failed to start agent: {result.stderr}"
            if log_result.returncode == 0 and log_result.stdout:
                error_msg += f"\n\nAgent log:\n{log_result.stdout}"
            raise SandboxStartupError(error_msg)
