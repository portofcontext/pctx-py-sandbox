#!/usr/bin/env python3
"""
Debug script to monitor worker pool behavior and identify failure patterns.

This script stress-tests the worker pool under various load conditions
to identify when and why workers fail.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pctx_sandbox.agent.pool import WarmSandboxPool

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


async def test_pool_sequential_execution(pool_size: int = 2, execution_count: int = 10):
    """Execute jobs sequentially through the pool."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"TEST 1: Sequential Execution (pool={pool_size}, jobs={execution_count})")
    logger.info(f"{'=' * 60}\n")

    async with WarmSandboxPool(pool_size=pool_size) as pool:
        successes = 0
        failures = 0

        for i in range(execution_count):
            logger.info(f"Executing job {i + 1}/{execution_count}")
            try:

                def simple_func(x: int) -> int:
                    return x * 2

                result = await pool.execute(simple_func, 42)
                if result == 84:
                    successes += 1
                    logger.info(f"  ✓ Job {i + 1} succeeded")
                else:
                    failures += 1
                    logger.error(f"  ✗ Job {i + 1} returned wrong result: {result}")
            except Exception as e:
                failures += 1
                logger.error(f"  ✗ Job {i + 1} failed: {e}")

            await asyncio.sleep(0.1)  # Small delay between jobs

    logger.info(f"\n{'=' * 60}")
    logger.info(
        f"Sequential Test Results: {successes}/{execution_count} succeeded, {failures}/{execution_count} failed"
    )
    logger.info(f"{'=' * 60}\n")
    return successes, failures


async def test_pool_concurrent_execution(pool_size: int = 2, concurrent_count: int = 10):
    """Execute multiple jobs concurrently through the pool."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"TEST 2: Concurrent Execution (pool={pool_size}, jobs={concurrent_count})")
    logger.info(f"{'=' * 60}\n")

    async with WarmSandboxPool(pool_size=pool_size) as pool:

        async def run_job(job_id: int):
            logger.info(f"Starting job {job_id}")
            try:

                def simple_func(x: int) -> int:
                    return x * 2

                result = await pool.execute(simple_func, job_id)
                if result == job_id * 2:
                    logger.info(f"  ✓ Job {job_id} succeeded")
                    return True
                else:
                    logger.error(f"  ✗ Job {job_id} returned wrong result: {result}")
                    return False
            except Exception as e:
                logger.error(f"  ✗ Job {job_id} failed: {e}")
                return False

        # Run all jobs concurrently
        results = await asyncio.gather(*[run_job(i) for i in range(concurrent_count)])

        successes = sum(1 for r in results if r)
        failures = len(results) - successes

    logger.info(f"\n{'=' * 60}")
    logger.info(
        f"Concurrent Test Results: {successes}/{concurrent_count} succeeded, {failures}/{concurrent_count} failed"
    )
    logger.info(f"{'=' * 60}\n")
    return successes, failures


async def test_pool_rapid_execution(pool_size: int = 2, execution_count: int = 20):
    """Execute jobs as rapidly as possible (no delay)."""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"TEST 3: Rapid Sequential Execution (pool={pool_size}, jobs={execution_count})")
    logger.info(f"{'=' * 60}\n")

    async with WarmSandboxPool(pool_size=pool_size) as pool:
        successes = 0
        failures = 0

        for i in range(execution_count):
            try:

                def simple_func(x: int) -> int:
                    return x * 2

                result = await pool.execute(simple_func, i)
                if result == i * 2:
                    successes += 1
                else:
                    failures += 1
                    logger.error(f"  ✗ Job {i} returned wrong result: {result}")
            except Exception as e:
                failures += 1
                logger.error(f"  ✗ Job {i} failed: {e}")

    logger.info(f"\n{'=' * 60}")
    logger.info(
        f"Rapid Test Results: {successes}/{execution_count} succeeded, {failures}/{execution_count} failed"
    )
    logger.info(f"{'=' * 60}\n")
    return successes, failures


async def test_pool_stress(pool_size: int = 3, concurrent_batches: int = 5, batch_size: int = 10):
    """Stress test with multiple concurrent batches."""
    logger.info(f"\n{'=' * 60}")
    logger.info(
        f"TEST 4: Stress Test (pool={pool_size}, batches={concurrent_batches}, batch_size={batch_size})"
    )
    logger.info(f"{'=' * 60}\n")

    async with WarmSandboxPool(pool_size=pool_size) as pool:

        async def run_batch(batch_id: int):
            batch_successes = 0
            batch_failures = 0

            for i in range(batch_size):
                job_id = batch_id * batch_size + i
                try:

                    def simple_func(x: int) -> int:
                        return x * 2

                    result = await pool.execute(simple_func, job_id)
                    if result == job_id * 2:
                        batch_successes += 1
                    else:
                        batch_failures += 1
                except Exception as e:
                    batch_failures += 1
                    logger.error(f"  Batch {batch_id} job {i} failed: {e}")

            logger.info(
                f"Batch {batch_id} complete: {batch_successes}/{batch_size} succeeded, {batch_failures}/{batch_size} failed"
            )
            return batch_successes, batch_failures

        # Run batches concurrently
        batch_results = await asyncio.gather(*[run_batch(i) for i in range(concurrent_batches)])

        total_successes = sum(s for s, _ in batch_results)
        total_failures = sum(f for _, f in batch_results)
        total_jobs = concurrent_batches * batch_size

    logger.info(f"\n{'=' * 60}")
    logger.info(
        f"Stress Test Results: {total_successes}/{total_jobs} succeeded, {total_failures}/{total_jobs} failed"
    )
    logger.info(f"{'=' * 60}\n")
    return total_successes, total_failures


async def main():
    """Run all diagnostic tests."""
    logger.info("Starting Worker Pool Diagnostics\n")

    all_results = []

    # Test 1: Sequential (baseline - should have 100% success rate)
    s, f = await test_pool_sequential_execution(pool_size=2, execution_count=10)
    all_results.append(("Sequential (baseline)", s, f, s + f))

    # Test 2: Concurrent (tests pool management)
    s, f = await test_pool_concurrent_execution(pool_size=2, concurrent_count=10)
    all_results.append(("Concurrent", s, f, s + f))

    # Test 3: Rapid sequential (tests worker reuse)
    s, f = await test_pool_rapid_execution(pool_size=2, execution_count=20)
    all_results.append(("Rapid sequential", s, f, s + f))

    # Test 4: Stress test (tests under heavy load)
    s, f = await test_pool_stress(pool_size=3, concurrent_batches=5, batch_size=10)
    all_results.append(("Stress test", s, f, s + f))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Summary of All Tests")
    logger.info("=" * 60)

    for test_name, successes, failures, total in all_results:
        success_rate = (successes / total * 100) if total > 0 else 0
        status = "✓" if failures == 0 else "⚠"
        logger.info(
            f"  {status} {test_name}: {successes}/{total} ({success_rate:.1f}% success rate)"
        )

    total_successes = sum(s for _, s, _, _ in all_results)
    total_jobs = sum(t for _, _, _, t in all_results)
    overall_rate = (total_successes / total_jobs * 100) if total_jobs > 0 else 0

    logger.info(f"\nOverall: {total_successes}/{total_jobs} ({overall_rate:.1f}% success rate)")


if __name__ == "__main__":
    asyncio.run(main())
