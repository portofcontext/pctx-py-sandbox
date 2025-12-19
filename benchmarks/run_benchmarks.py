"""Simple benchmarks focused on execution performance."""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pctx_sandbox import sandbox, sandbox_async
from pctx_sandbox.platform import get_backend


def benchmark_simple_execution():
    """Benchmark basic function execution speed."""
    print("\n" + "=" * 80)
    print("Simple Execution")
    print("=" * 80)

    @sandbox()
    def simple_func(x: int) -> int:
        return x * 2

    # Warm up
    simple_func(1)

    # Measure warm execution
    timings = []
    for i in range(20):
        start = time.perf_counter()
        _ = simple_func(i)
        timings.append((time.perf_counter() - start) * 1000)

    print(f"Runs: {len(timings)}")
    print(f"Average: {sum(timings) / len(timings):.2f}ms")
    print(f"Median: {sorted(timings)[len(timings) // 2]:.2f}ms")
    print(f"Min: {min(timings):.2f}ms")
    print(f"Max: {max(timings):.2f}ms")


def benchmark_concurrent_execution():
    """Benchmark concurrent execution throughput."""
    print("\n" + "=" * 80)
    print("Concurrent Execution (20 jobs)")
    print("=" * 80)

    @sandbox()
    def concurrent_func(x: int) -> int:
        return x * 2

    # Warm up
    concurrent_func(1)

    # Measure concurrent throughput
    import concurrent.futures

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(concurrent_func, i) for i in range(20)]
        _ = [f.result() for f in futures]
    total_ms = (time.perf_counter() - start) * 1000

    print(f"Total time: {total_ms:.2f}ms")
    print(f"Throughput: {20 / (total_ms / 1000):.2f} jobs/sec")
    print(f"Avg per job: {total_ms / 20:.2f}ms")


async def benchmark_async_execution():
    """Benchmark async function execution."""
    print("\n" + "=" * 80)
    print("Async Execution (20 concurrent)")
    print("=" * 80)

    @sandbox_async()
    async def async_func(x: int) -> int:
        return x * 2

    # Warm up
    await async_func(1)

    # Measure concurrent async
    start = time.perf_counter()
    _ = await asyncio.gather(*[async_func(i) for i in range(20)])
    total_ms = (time.perf_counter() - start) * 1000

    print(f"Total time: {total_ms:.2f}ms")
    print(f"Throughput: {20 / (total_ms / 1000):.2f} jobs/sec")
    print(f"Avg per job: {total_ms / 20:.2f}ms")


def benchmark_with_dependencies():
    """Benchmark execution with dependency installation (cached vs uncached)."""
    print("\n" + "=" * 80)
    print("With Dependencies (numpy) - Cache Impact")
    print("=" * 80)

    print("\n1. No cache (disable_cache=True)...")
    print("   Testing 3 runs with cache disabled - each should install numpy fresh")

    @sandbox(dependencies=["numpy"], disable_cache=True)
    def numpy_func_no_cache(size: int) -> float:
        import numpy as np

        arr = np.random.rand(size)
        return float(arr.mean())

    # Run 3 times with cache disabled - each should be slow
    no_cache_timings = []
    for i in range(3):
        start = time.perf_counter()
        _ = numpy_func_no_cache(100)
        duration = (time.perf_counter() - start) * 1000
        no_cache_timings.append(duration)
        print(f"   Run {i + 1}: {duration:.2f}ms")

    avg_no_cache = sum(no_cache_timings) / len(no_cache_timings)
    print(f"   Average (no cache): {avg_no_cache:.2f}ms")

    print("\n2. With cache (disable_cache=False, default)...")
    print("   First run will install, subsequent runs use cache")

    @sandbox(dependencies=["numpy"])
    def numpy_func_with_cache(size: int) -> float:
        import numpy as np

        arr = np.random.rand(size)
        return float(arr.mean())

    # First run - cold start
    start = time.perf_counter()
    _ = numpy_func_with_cache(100)
    first_run_ms = (time.perf_counter() - start) * 1000
    print(f"   First run (cold): {first_run_ms:.2f}ms")

    # Subsequent runs - should use cache
    cached_timings = []
    for _i in range(5):
        start = time.perf_counter()
        _ = numpy_func_with_cache(100)
        duration = (time.perf_counter() - start) * 1000
        cached_timings.append(duration)

    avg_cached = sum(cached_timings) / len(cached_timings)
    print(
        f"   Warm runs (5x): avg={avg_cached:.2f}ms, min={min(cached_timings):.2f}ms, max={max(cached_timings):.2f}ms"
    )

    speedup = avg_no_cache / avg_cached
    print(f"\n   Cache speedup: {speedup:.1f}x faster (cached vs no-cache)")


def benchmark_container_startup():
    """Benchmark container initialization."""
    print("\n" + "=" * 80)
    print("Container Operations")
    print("=" * 80)

    backend = get_backend()

    # Health check
    start = time.perf_counter()
    is_running = backend.is_running()
    health_check_ms = (time.perf_counter() - start) * 1000

    print(f"Health check: {health_check_ms:.2f}ms")
    print(f"Status: {'Running' if is_running else 'Stopped'}")

    if not is_running:
        # Startup time
        start = time.perf_counter()
        backend.ensure_running()
        startup_ms = (time.perf_counter() - start) * 1000
        print(f"Cold startup: {startup_ms:.2f}ms")


def main():
    """Run all benchmarks."""
    print("\n" + "=" * 80)
    print("pctx-sandbox Performance Benchmarks")
    print("=" * 80)

    try:
        # Container operations
        benchmark_container_startup()

        # Simple execution (most important - baseline speed)
        benchmark_simple_execution()

        # Concurrent execution (throughput)
        benchmark_concurrent_execution()

        # Async execution (async throughput)
        asyncio.run(benchmark_async_execution())

        # With dependencies (cold vs warm)
        benchmark_with_dependencies()

        print("\n" + "=" * 80)
        print("Benchmarks Complete!")
        print("=" * 80)
        print("\nKey metrics to watch:")
        print("  - Simple execution average: Lower is better")
        print("  - Concurrent throughput: Higher is better")
        print("  - Warm execution after deps: Should be fast")

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
