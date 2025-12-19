"""Pytest configuration and shared fixtures."""

import pytest

from pctx_sandbox.platform import get_backend


def pytest_collection_modifyitems(config, items):
    """Automatically skip tests that require sandbox agent when it's not available."""
    skip_agent = pytest.mark.skip(reason="Sandbox backend not available on this platform")

    for item in items:
        if "requires_sandbox_agent" in item.keywords:
            try:
                backend = get_backend()
                if not backend.is_available():
                    item.add_marker(skip_agent)
            except Exception:
                # If we can't get backend, skip the test
                item.add_marker(skip_agent)


@pytest.fixture
def mock_lima_output():
    """Mock output from limactl list --json."""
    return {
        "running": '[{"name":"pctx-sandbox","status":"Running"}]',
        "stopped": '[{"name":"pctx-sandbox","status":"Stopped"}]',
        "empty": "[]",
        "other_vm": '[{"name":"other-vm","status":"Running"}]',
    }


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
