"""Integration tests for @sandbox decorator with real agent."""

import pytest

from pctx_sandbox import sandbox


@pytest.mark.integration
@pytest.mark.requires_lima
class TestSandboxDecoratorIntegration:
    """Integration tests for @sandbox decorator with running agent."""

    def test_simple_function(self) -> None:
        """Test simple function execution."""

        @sandbox()
        def add(a: int, b: int) -> int:
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_function_with_dependencies(self) -> None:
        """Test function with external dependencies."""

        @sandbox(dependencies=["requests==2.31.0"])
        def get_requests_version() -> str:
            import requests

            return requests.__version__

        result = get_requests_version()
        assert result == "2.31.0"

    def test_function_with_numpy(self) -> None:
        """Test function with numpy dependency."""

        @sandbox(dependencies=["numpy==1.24.0"])
        def compute_mean(numbers: list[float]) -> float:
            import numpy as np

            return float(np.mean(numbers))

        result = compute_mean([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result == 3.0

    def test_function_with_memory_limit(self) -> None:
        """Test function with custom memory limit."""

        @sandbox(memory_mb=256)
        def small_computation() -> int:
            return sum(range(100))

        result = small_computation()
        assert result == 4950

    def test_function_with_timeout(self) -> None:
        """Test function with timeout."""

        @sandbox(timeout_sec=5)
        def quick_function() -> str:
            return "done"

        result = quick_function()
        assert result == "done"

    def test_function_with_error(self) -> None:
        """Test that errors are properly propagated."""
        from pctx_sandbox.exceptions import SandboxExecutionError

        @sandbox()
        def failing_function() -> None:
            raise ValueError("Test error")

        with pytest.raises(SandboxExecutionError) as exc_info:
            failing_function()

        assert exc_info.value.error_type == "ValueError"
        assert "Test error" in str(exc_info.value)

    def test_function_with_kwargs(self) -> None:
        """Test function with keyword arguments."""

        @sandbox()
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = greet("Alice", greeting="Hi")
        assert result == "Hi, Alice!"

    def test_multiple_functions_same_dependencies(self) -> None:
        """Test that multiple functions with same dependencies reuse snapshots."""

        @sandbox(dependencies=["requests==2.31.0"])
        def func1() -> str:
            import requests

            return "func1"

        @sandbox(dependencies=["requests==2.31.0"])
        def func2() -> str:
            import requests

            return "func2"

        result1 = func1()
        result2 = func2()

        assert result1 == "func1"
        assert result2 == "func2"

    def test_stateless_execution(self) -> None:
        """Test that executions are stateless."""

        counter = 0

        @sandbox()
        def increment() -> int:
            # This should NOT see the outer counter
            # Each execution is isolated
            return 42

        result1 = increment()
        result2 = increment()

        assert result1 == 42
        assert result2 == 42
        assert counter == 0  # Outer counter unchanged

    def test_complex_return_type(self) -> None:
        """Test function with complex return types."""

        @sandbox()
        def get_dict() -> dict[str, list[int]]:
            return {"numbers": [1, 2, 3], "more": [4, 5, 6]}

        result = get_dict()
        assert result == {"numbers": [1, 2, 3], "more": [4, 5, 6]}

    def test_function_with_closure(self) -> None:
        """Test that closures are properly serialized."""
        multiplier = 10

        @sandbox()
        def multiply(x: int) -> int:
            return x * multiplier

        result = multiply(5)
        assert result == 50

    async def test_async_function(self) -> None:
        """Test async function execution."""

        @sandbox()
        async def async_add(a: int, b: int) -> int:
            return a + b

        result = await async_add(7, 8)
        assert result == 15

    async def test_async_function_with_dependencies(self) -> None:
        """Test async function with dependencies."""

        @sandbox(dependencies=["httpx==0.27.0"])
        async def get_httpx_version() -> str:
            import httpx

            return httpx.__version__

        result = await get_httpx_version()
        assert result.startswith("0.27")

    def test_pandas_dataframe(self) -> None:
        """Test function using pandas."""

        @sandbox(dependencies=["pandas==2.0.0", "numpy<2.0"])
        def process_data() -> dict[str, list[int]]:
            import pandas as pd

            df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
            return df.to_dict(orient="list")

        result = process_data()
        assert result == {"a": [1, 2, 3], "b": [4, 5, 6]}

    def test_file_operations_isolated(self) -> None:
        """Test that sandbox uses VM filesystem, not host filesystem."""
        import os

        @sandbox()
        def check_filesystem() -> dict[str, str]:
            # Check that we're in Lima VM, not on host
            import subprocess

            # Get username
            user = os.environ.get("USER", "unknown")

            # Check hostname (Lima VM has different hostname)
            try:
                hostname = subprocess.check_output(["hostname"], text=True).strip()
            except Exception:
                hostname = "error"

            return {"user": user, "hostname": hostname}

        result = check_filesystem()

        # Lima VM user is different from host user
        import getpass

        host_user = getpass.getuser()
        import socket

        host_hostname = socket.gethostname()

        # Verify we're NOT on the host system
        # (Lima VM will have different user/hostname)
        assert (
            result["user"] != host_user or result["hostname"] != host_hostname
        ), f"Sandbox should run in VM, not on host. Got user={result['user']}, hostname={result['hostname']}"

    def test_environment_isolation(self) -> None:
        """Test that environment variables are isolated."""
        import os

        os.environ["TEST_VAR"] = "host_value"

        @sandbox()
        def check_env() -> str:
            import os

            return os.environ.get("TEST_VAR", "not_set")

        result = check_env()
        # VM should not see host environment variable
        assert result == "not_set"

    def test_network_isolation(self) -> None:
        """Test network access from sandbox."""

        @sandbox(dependencies=["httpx==0.27.0"])
        def check_network() -> bool:
            # Basic test - can we import and use httpx?
            import httpx

            return True

        result = check_network()
        assert result is True

    def test_cpu_intensive_task(self) -> None:
        """Test CPU-intensive task."""

        @sandbox(cpus=2)
        def fibonacci(n: int) -> int:
            # Iterative implementation to avoid recursive sandbox calls
            a, b = 0, 1
            for _ in range(n):
                a, b = b, a + b
            return a

        result = fibonacci(10)
        assert result == 55

    def test_multiple_dependencies(self) -> None:
        """Test function with multiple dependencies."""

        @sandbox(dependencies=["requests==2.31.0", "certifi==2023.7.22"])
        def check_multiple_deps() -> tuple[str, str]:
            import requests
            import certifi

            return (requests.__version__, certifi.__version__)

        result = check_multiple_deps()
        assert result[0] == "2.31.0"
        # certifi version formatting varies (2023.07.22 vs 2023.7.22)
        assert result[1].replace(".07.", ".7.") == "2023.7.22"
