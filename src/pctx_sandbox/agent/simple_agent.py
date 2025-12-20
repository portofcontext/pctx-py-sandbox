"""Simple sandbox agent - runs in Podman container, executes functions in isolated processes.

This agent provides sandboxing using Podman containers with warm process pools for fast execution.
"""

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any

import msgpack
from fastapi import FastAPI, Request, Response

# Support both relative and absolute imports for standalone execution
try:
    from .pool import WarmSandboxPool
except ImportError:
    from pool import WarmSandboxPool  # type: ignore[no-redef]

app = FastAPI()


class SimpleExecutor:
    """Executes functions in isolated Python processes using warm pools inside Podman container."""

    def __init__(
        self,
        cache_dir: Path = Path("/tmp/pctx-cache"),
        pool_size: int = 3,
    ) -> None:
        """Initialize executor.

        Args:
            cache_dir: Directory for dependency caches
            pool_size: Number of warm workers to maintain per venv (default: 3)
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.dep_envs: dict[str, Path] = {}

        # Pools per dependency hash
        self.pools: dict[str, WarmSandboxPool] = {}
        self.pool_size = pool_size
        self.platform = sys.platform

    async def execute(
        self,
        fn_pickle: bytes,
        args_pickle: bytes,
        kwargs_pickle: bytes,
        dependencies: list[str],
        dep_hash: str,
        timeout_sec: int = 30,
        memory_mb: int = 1024,
        cpus: int = 1,
    ) -> dict[str, Any]:
        """Execute a function in an isolated process using warm pool.

        Args:
            fn_pickle: Pickled function
            args_pickle: Pickled args
            kwargs_pickle: Pickled kwargs
            dependencies: List of pip packages
            dep_hash: Hash of dependencies
            timeout_sec: Execution timeout
            memory_mb: Memory limit
            cpus: CPU count

        Returns:
            Result dictionary
        """
        # Ensure dependencies are installed using uv
        venv_path = await self._ensure_venv(dep_hash, dependencies)

        # Get or create pool for this dependency set
        pool = await self._ensure_pool(dep_hash, venv_path)

        # Execute using the warm pool
        return await pool.execute(
            fn_pickle=fn_pickle,
            args_pickle=args_pickle,
            kwargs_pickle=kwargs_pickle,
            timeout_sec=timeout_sec,
            memory_mb=memory_mb,
            cpus=cpus,
        )

    async def _ensure_venv(self, dep_hash: str, dependencies: list[str]) -> Path | None:
        """Ensure virtual environment with dependencies exists using uv.

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

        # If venv already exists on disk, reuse it
        if venv_path.exists() and (venv_path / "bin" / "python").exists():
            self.dep_envs[dep_hash] = venv_path
            return venv_path

        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Creating venv at {venv_path} with Python {sys.executable}")

        proc = await asyncio.create_subprocess_exec(
            "uv",
            "venv",
            "--python",
            sys.executable,
            str(venv_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        returncode = await proc.wait()
        stdout_data = await proc.stdout.read() if proc.stdout else b""
        stderr_data = await proc.stderr.read() if proc.stderr else b""

        if returncode != 0:
            raise RuntimeError(f"Failed to create venv at {venv_path}: {stderr_data.decode()}")

        logger.info(f"Venv created. stdout: {stdout_data.decode()[:200]}")

        # Install dependencies using uv (much faster and more reliable than pip)
        # Worker needs: cloudpickle (for serialization), fastapi+uvicorn (for HTTP server)
        all_deps = ["cloudpickle", "fastapi", "uvicorn", *dependencies]
        venv_python_path = str(venv_path / "bin" / "python")

        logger.info(f"Installing {len(all_deps)} packages to {venv_python_path}: {all_deps}")

        proc = await asyncio.create_subprocess_exec(
            "uv",
            "pip",
            "install",
            "--python",
            venv_python_path,
            "--no-cache",
            *all_deps,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        returncode = await proc.wait()
        stdout_data = await proc.stdout.read() if proc.stdout else b""
        stderr_data = await proc.stderr.read() if proc.stderr else b""

        if returncode != 0:
            raise RuntimeError(f"Failed to install dependencies: {stderr_data.decode()}")

        logger.info(f"Packages installed. Last 500 chars of output: {stdout_data.decode()[-500:]}")

        self.dep_envs[dep_hash] = venv_path
        return venv_path

    async def _ensure_pool(self, dep_hash: str, venv_path: Path | None) -> WarmSandboxPool:
        """Ensure a warm pool exists for this dependency set.

        Args:
            dep_hash: Hash of dependencies
            venv_path: Path to venv or None

        Returns:
            Pool instance
        """
        if dep_hash in self.pools:
            return self.pools[dep_hash]

        # Create new pool
        pool = WarmSandboxPool(
            pool_size=self.pool_size,
            venv_path=venv_path,
        )

        await pool.start()
        self.pools[dep_hash] = pool

        return pool

    async def shutdown(self) -> None:
        """Shutdown all pools gracefully."""
        await asyncio.gather(
            *[pool.shutdown() for pool in self.pools.values()],
            return_exceptions=True,
        )


executor = SimpleExecutor()


@app.post("/execute")
async def execute(request: Request) -> Response:
    """Execute a function in isolated process.

    Args:
        request: HTTP request with msgpack payload

    Returns:
        msgpack-encoded result (always returns msgpack, even for errors)
    """
    try:
        body = await request.body()
        data = msgpack.unpackb(body)

        result = await executor.execute(
            fn_pickle=data["fn_pickle"],
            args_pickle=data["args_pickle"],
            kwargs_pickle=data["kwargs_pickle"],
            dependencies=data.get("dependencies", []),
            dep_hash=data.get("dep_hash", "none"),
            timeout_sec=data.get("timeout_sec", 30),
            memory_mb=data.get("memory_mb", 1024),
            cpus=data.get("cpus", 1),
        )

        return Response(content=msgpack.packb(result), media_type="application/msgpack")

    except Exception as e:
        # Always return msgpack-encoded error response
        error_result = {
            "error": True,
            "error_type": type(e).__name__,
            "error_message": str(e),
        }
        return Response(content=msgpack.packb(error_result), media_type="application/msgpack")


def _compute_agent_version() -> str:
    """Compute version hash from agent source files.

    This allows detecting when agent code has changed and needs reloading.
    """
    agent_dir = Path(__file__).parent
    files_to_hash = ["simple_agent.py", "pool.py", "worker.py"]

    hasher = hashlib.sha256()
    for filename in sorted(files_to_hash):  # Sort for consistency
        file_path = agent_dir / filename
        if file_path.exists():
            hasher.update(file_path.read_bytes())

    return hasher.hexdigest()[:16]  # First 16 chars of hash


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@app.get("/version")
async def version() -> dict[str, str]:
    """Return agent version hash based on source files.

    This allows clients to detect when agent code has changed.
    """
    return {"version": _compute_agent_version()}


@app.get("/status")
async def status() -> dict[str, Any]:
    """Status endpoint."""
    return {
        "cached_envs": list(executor.dep_envs.keys()),
        "cache_dir": str(executor.cache_dir),
        "pools": {dep_hash: pool.stats() for dep_hash, pool in executor.pools.items()},
    }


if __name__ == "__main__":
    import logging
    import os

    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting sandbox agent in Podman container...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Working directory: {os.getcwd()}")

    try:
        uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")
    except Exception as e:
        logger.error(f"Failed to start uvicorn: {e}", exc_info=True)
        raise
