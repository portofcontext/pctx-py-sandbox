"""Load tests for concurrent sandbox execution."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from pctx_sandbox import sandbox


class TestConcurrentLoad:
    """Test concurrent execution and retry behavior under load."""

    def test_concurrent_requests_sync(self) -> None:
        """Test many concurrent synchronous requests."""

        @sandbox()
        def compute(x: int) -> int:
            return x * 2

        # Spawn more requests than the pool size (default 5 workers)
        num_requests = 20
        start = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(compute, i) for i in range(num_requests)]

            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    pytest.fail(f"Request failed: {e}")

        elapsed = time.time() - start

        # Verify all results
        assert len(results) == num_requests
        assert sorted(results) == [i * 2 for i in range(num_requests)]

        print(f"\n{num_requests} concurrent requests completed in {elapsed:.2f}s")

    async def test_concurrent_requests_async(self) -> None:
        """Test many concurrent asynchronous requests."""

        @sandbox()
        async def compute(x: int) -> int:
            return x * 2

        # Spawn more requests than the pool size
        num_requests = 20
        start = time.time()

        tasks = [compute(i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start

        # Verify all results
        assert len(results) == num_requests
        assert sorted(results) == [i * 2 for i in range(num_requests)]

        print(f"\n{num_requests} concurrent async requests completed in {elapsed:.2f}s")

    def test_retry_on_worker_failure(self) -> None:
        """Test that client retries when workers fail."""

        @sandbox(dependencies=["requests==2.31.0"])
        def get_version() -> str:
            import requests  # type: ignore[import-untyped]

            return requests.__version__

        # Make multiple requests - some may hit unhealthy workers
        # but should succeed due to retries
        results = []
        for i in range(10):
            result = get_version()
            results.append(result)
            assert result == "2.31.0", f"Request {i} failed"

        print(f"\n{len(results)} requests completed successfully with retries")

    def test_high_concurrency_with_dependencies(self) -> None:
        """Test high concurrency with dependency installation."""

        @sandbox(dependencies=["httpx==0.27.0"])
        def get_httpx_version() -> str:
            import httpx

            return httpx.__version__

        num_requests = 15
        start = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_httpx_version) for _ in range(num_requests)]

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        elapsed = time.time() - start

        # All should succeed
        assert len(results) == num_requests
        assert all(r == "0.27.0" for r in results)

        print(f"\n{num_requests} concurrent requests with dependencies in {elapsed:.2f}s")
        print(f"Average: {elapsed / num_requests:.3f}s per request")
