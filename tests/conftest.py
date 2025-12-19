"""Pytest configuration and shared fixtures."""

import time

import httpx
import pytest

from pctx_sandbox.platform import get_backend


def pytest_collection_modifyitems(config, items):
    """Automatically skip tests that require sandbox agent when it's not available.

    Also mark sandbox agent tests for retry on worker pool exhaustion.
    """
    skip_agent = pytest.mark.skip(reason="Sandbox backend not available on this platform")
    # Retry tests that fail with WorkerDied errors (pool exhaustion)
    flaky = pytest.mark.flaky(reruns=2, reruns_delay=1, condition=lambda: True)

    for item in items:
        if "requires_sandbox_agent" in item.keywords:
            try:
                backend = get_backend()
                if not backend.is_available():
                    item.add_marker(skip_agent)
                else:
                    # Add flaky marker to handle intermittent pool exhaustion
                    item.add_marker(flaky)
            except Exception:
                # If we can't get backend, skip the test
                item.add_marker(skip_agent)


@pytest.fixture(autouse=True)
def ensure_pool_health(request):
    """Ensure worker pool is healthy before tests that use the sandbox.

    This prevents cascading failures due to pool exhaustion.
    """
    # Only run for tests marked as requiring sandbox agent
    if "requires_sandbox_agent" not in request.keywords:
        yield
        return

    # Before test: wait for at least one healthy worker
    try:
        backend = get_backend()
        if backend.is_available():
            max_wait = 5  # seconds
            start = time.time()
            while time.time() - start < max_wait:
                try:
                    # Simple health check - if this succeeds, pool has workers
                    with httpx.Client(timeout=1) as client:
                        response = client.get(f"{backend.agent_url}/health")
                        if response.status_code == 200:
                            break
                except Exception:
                    pass
                time.sleep(0.2)
    except Exception:
        pass

    yield

    # After test, brief pause to let any async cleanup happen
    time.sleep(0.05)


@pytest.fixture
def sample_function():
    """A sample function to be sandboxed."""

    def add(a: int, b: int) -> int:
        return a + b

    return add


@pytest.fixture
def sample_function_with_deps():
    """A sample function that requires dependencies."""

    def process_with_pandas(data: list) -> int:
        import pandas as pd  # type: ignore[import-untyped]

        df = pd.DataFrame(data)
        return len(df)

    return process_with_pandas
