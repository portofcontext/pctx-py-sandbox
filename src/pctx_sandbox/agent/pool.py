"""Warm sandbox pool for process isolation inside Podman container."""

import asyncio
import base64
import logging
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SandboxWorker:
    """A single warm worker process (container provides isolation)."""

    def __init__(
        self,
        worker_id: int,
        python_bin: Path | str,
        memory_mb: int = 512,
        cpus: int = 1,
    ) -> None:
        """Initialize worker.

        Args:
            worker_id: Unique worker identifier
            python_bin: Path to Python interpreter
            memory_mb: Memory limit in MB (unused, container-level limit applies)
            cpus: CPU count (unused, container-level limit applies)
        """
        self.worker_id = worker_id
        self.python_bin = python_bin
        self.memory_mb = memory_mb
        self.cpus = cpus

        self.process: asyncio.subprocess.Process | None = None
        self.worker_url: str | None = None  # HTTP URL of worker (e.g., http://127.0.0.1:12345)
        self.is_healthy = True
        self.is_busy = False
        self.jobs_executed = 0
        self.created_at = time.time()
        self.last_used_at = time.time()

    async def start(self) -> None:
        """Start the worker process and wait for it to be ready.

        This method:
        1. Spawns Python process running worker.py HTTP server via uvx
        2. Waits for worker to write "READY:PORT" to stdout
        3. Verifies worker is healthy with HTTP health check
        4. Returns only when worker is definitely ready to accept jobs
        """
        # Get worker script path
        worker_script = Path(__file__).parent / "worker.py"
        logger.debug(f"Worker {self.worker_id}: script path = {worker_script}")
        logger.debug(f"Worker {self.worker_id}: script exists = {worker_script.exists()}")

        cmd = [
            str(self.python_bin),
            str(worker_script),
        ]
        logger.debug(f"Worker {self.worker_id}: starting with command: {' '.join(cmd)}")

        # Start the process
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,  # Worker doesn't need stdin for HTTP mode
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.debug(f"Worker {self.worker_id}: process started with PID {self.process.pid}")

        # Wait for worker to signal readiness with port number
        # This blocks until worker has actually started HTTP server
        if not self.process.stdout:
            raise RuntimeError(f"Worker {self.worker_id} stdout is None")

        try:
            ready_line = await asyncio.wait_for(
                self.process.stdout.readline(),
                timeout=10.0,  # Generous timeout for Python startup
            )
        except asyncio.TimeoutError as e:
            await self.shutdown()
            raise RuntimeError(
                f"Worker {self.worker_id} did not signal readiness within 10 seconds"
            ) from e

        # Parse "READY:PORT\n"
        ready_text = ready_line.decode().strip()
        if not ready_text.startswith("READY:"):
            # Read stderr to understand what went wrong
            stderr_output = ""
            if self.process and self.process.stderr:
                try:
                    # Give more time for error output to be written
                    stderr_bytes = await asyncio.wait_for(
                        self.process.stderr.read(10000), timeout=5.0
                    )
                    stderr_output = stderr_bytes.decode()
                except asyncio.TimeoutError:
                    stderr_output = "(stderr read timed out)"
                except Exception as e:
                    logger.warning(f"Failed to read stderr: {e}")
                    stderr_output = f"(failed to read stderr: {e})"

            await self.shutdown()
            raise RuntimeError(
                f"Worker {self.worker_id} sent invalid ready signal: {ready_text}\n"
                f"stderr: {stderr_output}"
            )

        port = int(ready_text.split(":")[1])
        self.worker_url = f"http://127.0.0.1:{port}"
        logger.debug(f"Worker {self.worker_id}: ready on {self.worker_url}")

        # Verify with health check (with retries for robustness)
        max_health_retries = 3
        for attempt in range(max_health_retries):
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(f"{self.worker_url}/health")
                    if response.status_code != 200:
                        raise RuntimeError(
                            f"Health check failed with status {response.status_code}"
                        )
                    logger.debug(f"Worker {self.worker_id}: health check passed")
                    break  # Success!
            except httpx.ConnectError as e:
                if attempt < max_health_retries - 1:
                    # Exponential backoff: 0.1s, 0.2s
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
                # Final attempt failed
                await self.shutdown()
                raise RuntimeError(
                    f"Worker {self.worker_id} health check failed after {max_health_retries} attempts: {e}"
                ) from e
            except Exception as e:
                await self.shutdown()
                raise RuntimeError(f"Worker {self.worker_id} health check failed: {e}") from e

    async def execute(
        self, fn_pickle: bytes, args_pickle: bytes, kwargs_pickle: bytes, timeout_sec: int
    ) -> dict[str, Any]:
        """Execute a job on this worker via HTTP.

        Args:
            fn_pickle: Pickled function
            args_pickle: Pickled args
            kwargs_pickle: Pickled kwargs
            timeout_sec: Execution timeout

        Returns:
            Result dictionary
        """
        if not self.worker_url:
            raise RuntimeError(f"Worker {self.worker_id} not started")

        self.is_busy = True
        self.last_used_at = time.time()

        try:
            logger.debug(f"Worker {self.worker_id}: executing job with timeout {timeout_sec}s")

            # Prepare HTTP request payload
            payload = {
                "fn_pickle": base64.b64encode(fn_pickle).decode("ascii"),
                "args_pickle": base64.b64encode(args_pickle).decode("ascii"),
                "kwargs_pickle": base64.b64encode(kwargs_pickle).decode("ascii"),
            }

            # Send HTTP POST to worker
            async with httpx.AsyncClient(timeout=timeout_sec + 5) as client:
                response = await client.post(
                    f"{self.worker_url}/execute",
                    json=payload,
                    timeout=timeout_sec + 5,  # Add buffer for HTTP overhead
                )

            # Parse response
            result = response.json()

            # Convert result_pickle from base64 string to bytes
            # (don't unpickle here - let the caller handle that)
            if not result.get("error") and "result_pickle" in result:
                result["result_pickle"] = base64.b64decode(result["result_pickle"])

            self.jobs_executed += 1
            logger.debug(f"Worker {self.worker_id}: job completed")
            return result

        except (httpx.TimeoutException, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout):
            self.is_healthy = False
            return {
                "error": True,
                "error_type": "Timeout",
                "error_message": f"Execution exceeded {timeout_sec}s timeout",
            }
        except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
            self.is_healthy = False

            # Check if worker process is actually dead
            process_status = "unknown"
            if self.process:
                returncode = self.process.returncode
                if returncode is not None:
                    process_status = f"dead (exit code {returncode})"
                else:
                    process_status = "alive"

            logger.error(
                f"Worker {self.worker_id} connection failed: {e} "
                f"(process status: {process_status}, url: {self.worker_url})"
            )

            return {
                "error": True,
                "error_type": "WorkerDied",
                "error_message": f"Worker process terminated or connection refused (process: {process_status})",
            }
        except Exception as e:
            self.is_healthy = False
            logger.error(f"Worker {self.worker_id} error: {e}")

            # Try to get stderr from process
            if self.process and self.process.stderr:
                try:
                    stderr_data = await asyncio.wait_for(
                        self.process.stderr.read(10000), timeout=0.1
                    )
                    if stderr_data:
                        stderr_text = stderr_data.decode("utf-8", errors="replace")
                        logger.error(f"Worker stderr:\n{stderr_text}")
                except Exception:
                    pass

            return {
                "error": True,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
        finally:
            self.is_busy = False

    async def shutdown(self) -> None:
        """Gracefully shutdown the worker."""
        if self.process:
            try:
                # Terminate the process
                self.process.terminate()

                # Wait for process to exit (with timeout)
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    # Force kill if it doesn't exit gracefully
                    self.process.kill()
                    await self.process.wait()
            except Exception:
                pass

    def age_seconds(self) -> float:
        """Get worker age in seconds."""
        return time.time() - self.created_at

    def idle_seconds(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_used_at


class WarmSandboxPool:
    """Pool of warm sandbox workers for fast execution."""

    def __init__(
        self,
        pool_size: int = 10,
        max_jobs_per_worker: int = 100,
        max_worker_age_seconds: float = 3600,
        max_idle_seconds: float = 300,
        venv_path: Path | None = None,
    ) -> None:
        """Initialize pool.

        Args:
            pool_size: Number of workers to maintain
            max_jobs_per_worker: Rotate workers after this many jobs
            max_worker_age_seconds: Rotate workers after this many seconds
            max_idle_seconds: Shutdown idle workers after this time
            venv_path: Optional venv path for Python interpreter
        """
        self.pool_size = pool_size
        self.max_jobs_per_worker = max_jobs_per_worker
        self.max_worker_age_seconds = max_worker_age_seconds
        self.max_idle_seconds = max_idle_seconds

        self.workers: list[SandboxWorker] = []
        self.next_worker_id = 0

        # Determine Python binary
        if venv_path:
            self.python_bin: Path | str = venv_path / "bin" / "python"
        else:
            import sys

            self.python_bin = sys.executable

        # Background task for pool management
        self._management_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the pool and warm up workers."""

        # Start initial workers - some may fail, keep trying until we have at least one
        healthy_workers = 0
        attempts = 0
        max_attempts = self.pool_size * 3  # Try up to 3x the pool size
        errors = []

        while healthy_workers < self.pool_size and attempts < max_attempts:
            try:
                await self._create_worker()
                healthy_workers += 1
            except Exception as e:
                error_msg = f"Attempt {attempts + 1}: {type(e).__name__}: {e}"
                logger.warning(f"Failed to create worker: {error_msg}")
                errors.append(error_msg)
                attempts += 1
                continue

        if healthy_workers == 0:
            error_summary = "\n".join(errors[-5:])  # Last 5 errors for context
            raise RuntimeError(
                f"Failed to create any healthy workers after {attempts} attempts.\n"
                f"Recent errors:\n{error_summary}"
            )

        logger.info(f"Started pool with {healthy_workers} healthy workers")

        # Start background management task
        self._management_task = asyncio.create_task(self._manage_pool())

    async def _create_worker(self, memory_mb: int = 1024, cpus: int = 1) -> SandboxWorker:
        """Create and start a new worker.

        Args:
            memory_mb: Memory limit
            cpus: CPU count

        Returns:
            Started worker
        """
        worker = SandboxWorker(
            worker_id=self.next_worker_id,
            python_bin=self.python_bin,
            memory_mb=memory_mb,
            cpus=cpus,
        )
        self.next_worker_id += 1

        await worker.start()
        self.workers.append(worker)

        return worker

    async def _get_worker(self) -> SandboxWorker | None:
        """Get an available worker from the pool.

        Returns:
            Available worker or None if all busy
        """
        # Find healthy, non-busy worker
        for worker in self.workers:
            if worker.is_healthy and not worker.is_busy:
                logger.debug(
                    f"Found available worker {worker.worker_id} "
                    f"(age: {time.time() - worker.created_at:.1f}s, "
                    f"jobs: {worker.jobs_executed})"
                )
                return worker

        logger.debug(
            f"No available workers (total: {len(self.workers)}, "
            f"healthy: {sum(1 for w in self.workers if w.is_healthy)}, "
            f"busy: {sum(1 for w in self.workers if w.is_busy)})"
        )
        return None

    async def execute(
        self,
        fn_pickle: bytes,
        args_pickle: bytes,
        kwargs_pickle: bytes,
        timeout_sec: int = 30,
        memory_mb: int = 1024,
        cpus: int = 1,
    ) -> dict[str, Any]:
        """Execute a job using a worker from the pool.

        Args:
            fn_pickle: Pickled function
            args_pickle: Pickled args
            kwargs_pickle: Pickled kwargs
            timeout_sec: Execution timeout
            memory_mb: Memory limit (for ad-hoc workers)
            cpus: CPU count (for ad-hoc workers)

        Returns:
            Result dictionary
        """
        # Try to get an available worker
        worker = await self._get_worker()

        # If no workers available, create an ad-hoc one
        if worker is None:
            logger.info(
                f"No workers available in pool, creating ad-hoc worker "
                f"(memory={memory_mb}MB, cpus={cpus})"
            )
            try:
                worker = await self._create_worker(memory_mb=memory_mb, cpus=cpus)
            except Exception as e:
                logger.error(f"Failed to create ad-hoc worker: {e}")
                return {
                    "error": True,
                    "error_type": "WorkerCreationFailed",
                    "error_message": f"Failed to create worker: {e}",
                }

        # Execute the job
        result = await worker.execute(fn_pickle, args_pickle, kwargs_pickle, timeout_sec)

        # Replace unhealthy workers immediately (not as background task)
        if not worker.is_healthy:
            # Don't wait for replacement - do it in background but ensure it happens
            asyncio.create_task(self._replace_worker(worker))

        return result

    async def _replace_worker(self, worker: SandboxWorker) -> None:
        """Replace an unhealthy or expired worker.

        Args:
            worker: Worker to replace
        """
        # Remove from pool
        if worker in self.workers:
            self.workers.remove(worker)

        # Shutdown old worker
        await worker.shutdown()

        # Create new worker if we're below pool size (with retries)
        if len(self.workers) < self.pool_size:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self._create_worker()
                    break  # Success
                except Exception as e:
                    logger.warning(
                        f"Failed to create replacement worker (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Failed to create replacement worker after {max_retries} attempts"
                        )
                    else:
                        # Brief delay before retry
                        await asyncio.sleep(0.5 * (2**attempt))

    async def _manage_pool(self) -> None:
        """Background task to manage pool health."""
        while True:
            await asyncio.sleep(5)  # Check every 5 seconds instead of 10

            # First priority: ensure we have minimum workers
            while len(self.workers) < self.pool_size:
                try:
                    logger.info(
                        f"Pool below target size ({len(self.workers)}/{self.pool_size}), creating worker"
                    )
                    await self._create_worker()
                except Exception as e:
                    logger.error(f"Failed to create worker during pool maintenance: {e}")
                    break  # Don't loop forever on errors

            # Check for workers that need rotation
            for worker in list(self.workers):
                should_rotate = (
                    not worker.is_healthy
                    or worker.jobs_executed >= self.max_jobs_per_worker
                    or worker.age_seconds() >= self.max_worker_age_seconds
                )

                if should_rotate and not worker.is_busy:
                    asyncio.create_task(self._replace_worker(worker))

            # Shutdown idle workers (keep at least pool_size)
            idle_workers = [
                w
                for w in self.workers
                if not w.is_busy and w.idle_seconds() >= self.max_idle_seconds
            ]

            for worker in idle_workers:
                if len(self.workers) > self.pool_size:
                    asyncio.create_task(self._replace_worker(worker))

    async def shutdown(self) -> None:
        """Shutdown the entire pool."""
        # Cancel management task
        if self._management_task:
            self._management_task.cancel()
            try:
                await self._management_task
            except asyncio.CancelledError:
                pass

        # Shutdown all workers
        await asyncio.gather(*[w.shutdown() for w in self.workers], return_exceptions=True)

        self.workers.clear()

    def stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "pool_size": len(self.workers),
            "healthy_workers": sum(1 for w in self.workers if w.is_healthy),
            "busy_workers": sum(1 for w in self.workers if w.is_busy),
            "total_jobs": sum(w.jobs_executed for w in self.workers),
            "workers": [
                {
                    "id": w.worker_id,
                    "healthy": w.is_healthy,
                    "busy": w.is_busy,
                    "jobs": w.jobs_executed,
                    "age_seconds": w.age_seconds(),
                    "idle_seconds": w.idle_seconds(),
                }
                for w in self.workers
            ],
        }
