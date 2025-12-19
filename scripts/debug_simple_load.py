#!/usr/bin/env python3
"""
Simple load test to identify when workers start failing.

This mimics the test suite pattern to reproduce the failures.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pctx_sandbox import sandbox


def test_sequential(count: int = 10):
    """Run simple tests sequentially."""
    print(f"\n{'=' * 60}")
    print(f"TEST 1: Sequential ({count} executions)")
    print(f"{'=' * 60}\n")

    @sandbox()
    def simple_func(x: int) -> int:
        return x * 2

    successes = 0
    failures = 0

    for i in range(count):
        try:
            start = time.time()
            result = simple_func(i)
            elapsed = time.time() - start

            if result == i * 2:
                successes += 1
                print(f"  ✓ Execution {i + 1}/{count} succeeded in {elapsed:.3f}s")
            else:
                failures += 1
                print(f"  ✗ Execution {i + 1}/{count} wrong result: {result}")
        except Exception as e:
            failures += 1
            print(f"  ✗ Execution {i + 1}/{count} failed: {e}")

        time.sleep(0.1)

    print(f"\nSequential: {successes}/{count} succeeded, {failures}/{count} failed")
    return successes, failures


def test_rapid(count: int = 20):
    """Run tests rapidly without delays."""
    print(f"\n{'=' * 60}")
    print(f"TEST 2: Rapid Sequential ({count} executions, no delay)")
    print(f"{'=' * 60}\n")

    @sandbox()
    def simple_func(x: int) -> int:
        return x * 2

    successes = 0
    failures = 0
    timings = []

    for i in range(count):
        try:
            start = time.time()
            result = simple_func(i)
            elapsed = time.time() - start
            timings.append(elapsed)

            if result == i * 2:
                successes += 1
            else:
                failures += 1
                print(f"  ✗ Execution {i + 1} wrong result: {result}")
        except Exception as e:
            failures += 1
            print(f"  ✗ Execution {i + 1} failed: {e}")

    if timings:
        avg_time = sum(timings) / len(timings)
        min_time = min(timings)
        max_time = max(timings)
        print(f"\nTiming: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")

    print(f"Rapid: {successes}/{count} succeeded, {failures}/{count} failed")
    return successes, failures


def test_burst(bursts: int = 5, burst_size: int = 5):
    """Run in bursts with delays between bursts."""
    print(f"\n{'=' * 60}")
    print(f"TEST 3: Burst Pattern ({bursts} bursts of {burst_size})")
    print(f"{'=' * 60}\n")

    @sandbox()
    def simple_func(x: int) -> int:
        return x * 2

    total_successes = 0
    total_failures = 0

    for burst_id in range(bursts):
        print(f"\nBurst {burst_id + 1}/{bursts}:")
        burst_successes = 0
        burst_failures = 0

        for i in range(burst_size):
            job_id = burst_id * burst_size + i
            try:
                result = simple_func(job_id)
                if result == job_id * 2:
                    burst_successes += 1
                else:
                    burst_failures += 1
                    print(f"  ✗ Job {i + 1} wrong result")
            except Exception as e:
                burst_failures += 1
                print(f"  ✗ Job {i + 1} failed: {e}")

        total_successes += burst_successes
        total_failures += burst_failures
        print(f"  Burst {burst_id + 1}: {burst_successes}/{burst_size} succeeded")

        # Delay between bursts
        time.sleep(0.5)

    total = bursts * burst_size
    print(f"\nBurst pattern: {total_successes}/{total} succeeded, {total_failures}/{total} failed")
    return total_successes, total_failures


def main():
    """Run all diagnostic tests."""
    print("Simple Load Testing Diagnostics")
    print("=" * 60)

    results = []

    # Test 1: Sequential (baseline)
    s, f = test_sequential(count=10)
    results.append(("Sequential (baseline)", s, f, s + f))

    # Test 2: Rapid (no delays)
    s, f = test_rapid(count=20)
    results.append(("Rapid sequential", s, f, s + f))

    # Test 3: Bursts
    s, f = test_burst(bursts=5, burst_size=5)
    results.append(("Burst pattern", s, f, s + f))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for test_name, successes, failures, total in results:
        success_rate = (successes / total * 100) if total > 0 else 0
        status = "✓" if failures == 0 else "⚠"
        print(f"  {status} {test_name}: {successes}/{total} ({success_rate:.1f}% success rate)")

    total_successes = sum(s for _, s, _, _ in results)
    total_jobs = sum(t for _, _, _, t in results)
    overall_rate = (total_successes / total_jobs * 100) if total_jobs > 0 else 0

    print(f"\nOverall: {total_successes}/{total_jobs} ({overall_rate:.1f}% success rate)")

    # Exit with error code if there were failures
    if total_failures := total_jobs - total_successes:
        print(f"\n⚠ {total_failures} failures detected")
        sys.exit(1)


if __name__ == "__main__":
    main()
