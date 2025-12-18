"""Simple sandbox agent - runs in Lima VM, executes functions in isolated processes.

This agent provides sandboxing without Firecracker by running each function
in a separate Python process within the Lima VM.
"""

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import cloudpickle
import msgpack
from fastapi import FastAPI, Request, Response

app = FastAPI()


class SimpleExecutor:
    """Executes functions in isolated Python processes with optional additional sandboxing."""

    def __init__(self, cache_dir: Path = Path("/tmp/pctx-cache")) -> None:
        """Initialize executor.

        Args:
            cache_dir: Directory for dependency caches
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.dep_envs: dict[str, Path] = {}

        # Detect available sandboxing tools
        self.use_firejail = shutil.which("firejail") is not None
        self.platform = sys.platform

    async def execute(
        self,
        fn_pickle: bytes,
        args_pickle: bytes,
        kwargs_pickle: bytes,
        dependencies: list[str],
        dep_hash: str,
        timeout_sec: int = 30,
    ) -> dict[str, Any]:
        """Execute a function in an isolated process.

        Args:
            fn_pickle: Pickled function
            args_pickle: Pickled args
            kwargs_pickle: Pickled kwargs
            dependencies: List of pip packages
            dep_hash: Hash of dependencies
            timeout_sec: Execution timeout

        Returns:
            Result dictionary
        """
        # Ensure dependencies are installed
        venv_path = await self._ensure_venv(dep_hash, dependencies)

        # Create temporary file for execution
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pkl", delete=False) as f:
            payload = {
                "fn_pickle": fn_pickle,
                "args_pickle": args_pickle,
                "kwargs_pickle": kwargs_pickle,
            }
            f.write(cloudpickle.dumps(payload))
            payload_file = f.name

        try:
            # Execute in isolated process
            python_bin = venv_path / "bin" / "python" if venv_path else "python3"

            # Script outputs result as base64-encoded cloudpickle to stdout
            script = f"""
import sys
import base64
import traceback
import asyncio
import cloudpickle

try:
    with open('{payload_file}', 'rb') as f:
        data = cloudpickle.load(f)

    fn = cloudpickle.loads(data['fn_pickle'])
    args = cloudpickle.loads(data['args_pickle'])
    kwargs = cloudpickle.loads(data['kwargs_pickle'])

    result = fn(*args, **kwargs)

    # Handle async functions
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)

    output = {{'error': False, 'result_pickle': cloudpickle.dumps(result)}}

except Exception as e:
    output = {{
        'error': True,
        'error_type': type(e).__name__,
        'error_message': str(e),
        'traceback': traceback.format_exc()
    }}

# Output result to stdout as base64
sys.stdout.buffer.write(base64.b64encode(cloudpickle.dumps(output)))
"""

            # Build command with optional sandboxing layer
            if self.use_firejail:
                # Use firejail for additional process-level sandboxing inside the VM
                cmd = [
                    "firejail",
                    "--quiet",
                    "--private-dev",  # Minimal /dev
                    "--noroot",  # Prevent root escalation
                    "--seccomp",  # Enable seccomp filtering
                    "--caps.drop=all",  # Drop all capabilities
                    "--nonewprivs",  # Prevent privilege escalation
                    "--net=none",  # No network access by default
                    "--",
                    str(python_bin),
                    "-c",
                    script,
                ]
            else:
                cmd = [str(python_bin), "-c", script]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "error": True,
                    "error_type": "Timeout",
                    "error_message": f"Execution exceeded {timeout_sec}s timeout",
                }

            # Check for execution errors
            if proc.returncode != 0:
                return {
                    "error": True,
                    "error_type": "ExecutionError",
                    "error_message": f"Process exited with code {proc.returncode}",
                    "traceback": stderr.decode() if stderr else "",
                }

            # Decode result from stdout
            import base64

            result_data = base64.b64decode(stdout)
            return cloudpickle.loads(result_data)

        finally:
            # Cleanup
            Path(payload_file).unlink(missing_ok=True)

    async def _ensure_venv(self, dep_hash: str, dependencies: list[str]) -> Path | None:
        """Ensure virtual environment with dependencies exists.

        Args:
            dep_hash: Hash of dependencies
            dependencies: List of pip packages

        Returns:
            Path to venv or None if no dependencies
        """
        if not dependencies:
            return None

        if dep_hash in self.dep_envs:
            return self.dep_envs[dep_hash]

        venv_path = self.cache_dir / f"venv-{dep_hash}"

        if venv_path.exists():
            self.dep_envs[dep_hash] = venv_path
            return venv_path

        # Create venv
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "-m",
            "venv",
            str(venv_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        # Install dependencies
        # Note: Cannot use firejail here as it would isolate the venv from the cache
        pip_bin = venv_path / "bin" / "pip"
        proc = await asyncio.create_subprocess_exec(
            str(pip_bin),
            "install",
            "--no-cache-dir",
            "cloudpickle",
            *dependencies,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        self.dep_envs[dep_hash] = venv_path
        return venv_path


executor = SimpleExecutor()


@app.post("/execute")
async def execute(request: Request) -> Response:
    """Execute a function in isolated process.

    Args:
        request: HTTP request with msgpack payload

    Returns:
        msgpack-encoded result
    """
    body = await request.body()
    data = msgpack.unpackb(body)

    result = await executor.execute(
        fn_pickle=data["fn_pickle"],
        args_pickle=data["args_pickle"],
        kwargs_pickle=data["kwargs_pickle"],
        dependencies=data.get("dependencies", []),
        dep_hash=data.get("dep_hash", "none"),
        timeout_sec=data.get("timeout_sec", 30),
    )

    return Response(content=msgpack.packb(result), media_type="application/msgpack")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@app.get("/status")
async def status() -> dict[str, Any]:
    """Status endpoint."""
    return {
        "cached_envs": list(executor.dep_envs.keys()),
        "cache_dir": str(executor.cache_dir),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
