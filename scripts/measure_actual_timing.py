#!/usr/bin/env python3
"""
Measure the ACTUAL timing of worker startup to see if there's a gap.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configure logging to show timestamps
logging.basicConfig(
    level=logging.DEBUG,
    format="T+%(relativeCreated)06dms [%(levelname)-8s] %(name)-25s: %(message)s",
)

logger = logging.getLogger(__name__)


async def measure_worker_startup():
    """Measure actual timing of worker startup."""
    from pctx_sandbox.agent.pool import SandboxWorker

    nsjail_config = Path(__file__).parent.parent / "src" / "pctx_sandbox" / "agent" / "nsjail.cfg"
    python_bin = Path(sys.executable)

    logger.info("=" * 80)
    logger.info("MEASURING ACTUAL WORKER STARTUP TIMING")
    logger.info("=" * 80)

    worker = SandboxWorker(
        worker_id=1,
        python_bin=python_bin,
        nsjail_config=nsjail_config,
        memory_mb=512,
        cpus=1,
    )

    logger.info("Starting worker.start()...")
    start_time = time.time()

    try:
        await worker.start()
        startup_duration = time.time() - start_time
        logger.info(f"✓ worker.start() completed in {startup_duration * 1000:.1f}ms")
        logger.info(f"  Worker URL: {worker.worker_url}")

        # Now immediately try to execute something
        logger.info("\nImmediately executing job (no delay)...")
        import cloudpickle

        def test_func(x: int) -> int:
            return x * 2

        fn_pickle = cloudpickle.dumps(test_func)
        args_pickle = cloudpickle.dumps((42,))
        kwargs_pickle = cloudpickle.dumps({})

        execute_start = time.time()
        try:
            result = await worker.execute(fn_pickle, args_pickle, kwargs_pickle, timeout_sec=5)
            execute_duration = time.time() - execute_start

            if result.get("error"):
                logger.error(
                    f"✗ FIRST execute() FAILED in {execute_duration * 1000:.1f}ms: {result.get('error_message')}"
                )
            else:
                logger.info(f"✓ FIRST execute() succeeded in {execute_duration * 1000:.1f}ms")

        except Exception as e:
            execute_duration = time.time() - execute_start
            logger.error(f"✗ FIRST execute() exception in {execute_duration * 1000:.1f}ms: {e}")

        # Try again after a delay
        logger.info("\nWaiting 0.5s then trying again...")
        await asyncio.sleep(0.5)

        execute_start = time.time()
        try:
            result = await worker.execute(fn_pickle, args_pickle, kwargs_pickle, timeout_sec=5)
            execute_duration = time.time() - execute_start

            if result.get("error"):
                logger.error(
                    f"✗ SECOND execute() FAILED in {execute_duration * 1000:.1f}ms: {result.get('error_message')}"
                )
            else:
                logger.info(f"✓ SECOND execute() succeeded in {execute_duration * 1000:.1f}ms")

        except Exception as e:
            execute_duration = time.time() - execute_start
            logger.error(f"✗ SECOND execute() exception in {execute_duration * 1000:.1f}ms: {e}")

    finally:
        logger.info("\nShutting down worker...")
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(measure_worker_startup())
