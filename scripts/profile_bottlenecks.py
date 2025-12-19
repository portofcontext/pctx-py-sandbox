#!/usr/bin/env python3
"""Profile performance bottlenecks in the sandbox system."""

import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.DEBUG,
    format="T+%(relativeCreated)06dms [%(levelname)-8s] %(name)-25s: %(message)s",
)

logger = logging.getLogger(__name__)


async def profile_single_worker_lifecycle():
    """Profile a single worker from creation to execution."""
    import cloudpickle

    from pctx_sandbox.agent.pool import SandboxWorker

    nsjail_config = Path(__file__).parent.parent / "src" / "pctx_sandbox" / "agent" / "nsjail.cfg"
    python_bin = Path(sys.executable)

    logger.info("=" * 80)
    logger.info("PROFILING SINGLE WORKER LIFECYCLE")
    logger.info("=" * 80)

    # Measure worker creation
    t0 = time.time()
    worker = SandboxWorker(
        worker_id=1,
        python_bin=python_bin,
        nsjail_config=nsjail_config,
        memory_mb=512,
        cpus=1,
    )
    t1 = time.time()
    logger.info(f"Worker object creation: {(t1 - t0) * 1000:.1f}ms")

    # Measure worker startup
    t0 = time.time()
    try:
        await worker.start()
        t1 = time.time()
        logger.info(f"✓ Worker startup: {(t1 - t0) * 1000:.1f}ms")
    except Exception as e:
        t1 = time.time()
        logger.error(f"✗ Worker startup FAILED after {(t1 - t0) * 1000:.1f}ms: {e}")
        return

    # Measure first execution (cold)
    def test_func(x: int) -> int:
        return x * 2

    fn_pickle = cloudpickle.dumps(test_func)
    args_pickle = cloudpickle.dumps((42,))
    kwargs_pickle = cloudpickle.dumps({})

    t0 = time.time()
    try:
        result = await worker.execute(fn_pickle, args_pickle, kwargs_pickle, timeout_sec=5)
        t1 = time.time()
        if result.get("error"):
            logger.error(
                f"✗ First execution FAILED in {(t1 - t0) * 1000:.1f}ms: {result.get('error_message')}"
            )
        else:
            logger.info(f"✓ First execution (cold): {(t1 - t0) * 1000:.1f}ms")
    except Exception as e:
        t1 = time.time()
        logger.error(f"✗ First execution exception in {(t1 - t0) * 1000:.1f}ms: {e}")

    # Measure second execution (warm)
    t0 = time.time()
    try:
        result = await worker.execute(fn_pickle, args_pickle, kwargs_pickle, timeout_sec=5)
        t1 = time.time()
        if result.get("error"):
            logger.error(
                f"✗ Second execution FAILED in {(t1 - t0) * 1000:.1f}ms: {result.get('error_message')}"
            )
        else:
            logger.info(f"✓ Second execution (warm): {(t1 - t0) * 1000:.1f}ms")
    except Exception as e:
        t1 = time.time()
        logger.error(f"✗ Second execution exception in {(t1 - t0) * 1000:.1f}ms: {e}")

    # Measure third execution (warm)
    t0 = time.time()
    try:
        result = await worker.execute(fn_pickle, args_pickle, kwargs_pickle, timeout_sec=5)
        t1 = time.time()
        if result.get("error"):
            logger.error(
                f"✗ Third execution FAILED in {(t1 - t0) * 1000:.1f}ms: {result.get('error_message')}"
            )
        else:
            logger.info(f"✓ Third execution (warm): {(t1 - t0) * 1000:.1f}ms")
    except Exception as e:
        t1 = time.time()
        logger.error(f"✗ Third execution exception in {(t1 - t0) * 1000:.1f}ms: {e}")

    await worker.shutdown()


async def profile_decorator_overhead():
    """Profile the @sandbox decorator to see where time is spent."""
    from pctx_sandbox import sandbox

    logger.info("=" * 80)
    logger.info("PROFILING @SANDBOX DECORATOR OVERHEAD")
    logger.info("=" * 80)

    # First call - includes client initialization
    @sandbox()
    def test1(x: int) -> int:
        return x * 2

    t0 = time.time()
    try:
        test1(42)
        t1 = time.time()
        logger.info(f"✓ First call (with client init): {(t1 - t0) * 1000:.1f}ms")
    except Exception as e:
        t1 = time.time()
        logger.error(f"✗ First call FAILED in {(t1 - t0) * 1000:.1f}ms: {e}")

    # Second call - client already initialized
    @sandbox()
    def test2(x: int) -> int:
        return x * 3

    t0 = time.time()
    try:
        test2(42)
        t1 = time.time()
        logger.info(f"✓ Second call (client warm): {(t1 - t0) * 1000:.1f}ms")
    except Exception as e:
        t1 = time.time()
        logger.error(f"✗ Second call FAILED in {(t1 - t0) * 1000:.1f}ms: {e}")

    # Third call
    @sandbox()
    def test3(x: int) -> int:
        return x * 4

    t0 = time.time()
    try:
        test3(42)
        t1 = time.time()
        logger.info(f"✓ Third call (client warm): {(t1 - t0) * 1000:.1f}ms")
    except Exception as e:
        t1 = time.time()
        logger.error(f"✗ Third call FAILED in {(t1 - t0) * 1000:.1f}ms: {e}")


async def profile_serialization_overhead():
    """Measure cloudpickle serialization/deserialization time."""
    import cloudpickle

    logger.info("=" * 80)
    logger.info("PROFILING SERIALIZATION OVERHEAD")
    logger.info("=" * 80)

    def simple_func(x: int) -> int:
        return x * 2

    # Measure function pickling
    t0 = time.time()
    fn_pickle = cloudpickle.dumps(simple_func)
    t1 = time.time()
    logger.info(f"Function pickle: {(t1 - t0) * 1000:.3f}ms ({len(fn_pickle)} bytes)")

    # Measure args pickling
    t0 = time.time()
    args_pickle = cloudpickle.dumps((42,))
    t1 = time.time()
    logger.info(f"Args pickle: {(t1 - t0) * 1000:.3f}ms ({len(args_pickle)} bytes)")

    # Measure kwargs pickling
    t0 = time.time()
    kwargs_pickle = cloudpickle.dumps({})
    t1 = time.time()
    logger.info(f"Kwargs pickle: {(t1 - t0) * 1000:.3f}ms ({len(kwargs_pickle)} bytes)")

    # Measure function unpickling
    t0 = time.time()
    cloudpickle.loads(fn_pickle)
    t1 = time.time()
    logger.info(f"Function unpickle: {(t1 - t0) * 1000:.3f}ms")

    # Measure result pickling
    result = 84
    t0 = time.time()
    result_pickle = cloudpickle.dumps(result)
    t1 = time.time()
    logger.info(f"Result pickle: {(t1 - t0) * 1000:.3f}ms ({len(result_pickle)} bytes)")


async def main():
    """Run all profiling tests."""
    await profile_serialization_overhead()
    await profile_single_worker_lifecycle()
    await profile_decorator_overhead()


if __name__ == "__main__":
    asyncio.run(main())
