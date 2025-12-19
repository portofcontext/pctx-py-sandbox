"""Lima backend for macOS."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from pctx_sandbox.exceptions import SandboxStartupError

from .base import SandboxBackend


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
        return shutil.which("limactl") is not None

    def is_running(self) -> bool:
        """Check if the sandbox VM is running."""
        result = subprocess.run(["limactl", "list", "--json"], capture_output=True, text=True)
        if result.returncode != 0:
            return False

        if not result.stdout.strip():
            return False

        data = json.loads(result.stdout)
        vms = [data] if isinstance(data, dict) else data

        for vm in vms:
            if vm["name"] == self.VM_NAME and vm["status"] == "Running":
                return True
        return False

    def vm_exists(self) -> bool:
        """Check if the sandbox VM exists (running or stopped)."""
        result = subprocess.run(["limactl", "list", "--json"], capture_output=True, text=True)
        if result.returncode != 0:
            return False

        if not result.stdout.strip():
            return False

        data = json.loads(result.stdout)
        vms = [data] if isinstance(data, dict) else data

        return any(vm["name"] == self.VM_NAME for vm in vms)

    def ensure_running(self) -> None:
        """Ensure the sandbox VM is created and running.

        Note: Lima availability is checked in get_backend() before this is called.
        """
        if not self.vm_exists():
            self._create_vm()

        if not self.is_running():
            self._start_vm()

    def _create_vm(self) -> None:
        """Create the Lima VM for sandbox agent."""
        subprocess.run(
            [
                "limactl",
                "create",
                "--name",
                self.VM_NAME,
                f"--cpus={self.cpus}",
                f"--memory={self.memory_gib}",
                f"--disk={self.disk_gib}",
                str(self._config_path),
            ],
            check=True,
        )
        self._start_vm()

    def _start_vm(self) -> None:
        """Start the Lima VM."""
        try:
            subprocess.run(
                ["limactl", "start", self.VM_NAME],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to start VM: {e}"
            if e.stderr:
                error_msg += f"\n\nLima error output:\n{e.stderr}"
            raise SandboxStartupError(error_msg) from e

    def stop(self) -> None:
        """Stop the sandbox VM."""
        subprocess.run(["limactl", "stop", self.VM_NAME])

    def destroy(self) -> None:
        """Destroy the sandbox VM completely."""
        subprocess.run(["limactl", "delete", "--force", self.VM_NAME])
