"""Pytest configuration and shared fixtures."""

import pytest


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
